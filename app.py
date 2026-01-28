# ==========================================
# 文件: app.py
# 说明：Streamlit主程序，包含UI交互与核心逻辑
# 作者：lk (569261093@qq.com)
# 版本：1.3.0
# ==========================================
import json
import os
import re
from datetime import datetime

import streamlit as st
import yaml
from openai import OpenAI

from security_utils import decrypt_api_key, get_machine_code

# ---------------------------------------------------------
# 1. 初始化与配置加载
# ---------------------------------------------------------

def load_config():
    """加载配置文件"""
    try:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        st.error("❌ 未找到配置文件 config.yaml，请检查文件路径。")
        st.stop()
    except UnicodeDecodeError:
        st.error("❌ 配置文件编码错误，请保存为 UTF-8。")
        st.stop()
    except yaml.YAMLError as exc:
        st.error(f"❌ 配置文件格式错误：{exc}")
        st.stop()


# 加载配置
CONFIG = load_config()
APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_SETTINGS = CONFIG.get("app_settings", {})
UI_SETTINGS = CONFIG.get("ui_settings", {})
FILE_SETTINGS = CONFIG.get("file_settings", {})
SUBJECT_SETTINGS = CONFIG.get("subject_settings", {})
SUBJECT_GUIDANCE = CONFIG.get("subject_guidance", {})
SUBJECT_LIBRARY = CONFIG.get("subject_library", {})
LEARNING_SCOPE = CONFIG.get("learning_scope", {})
WRITING_SETTINGS = CONFIG.get("writing_settings", {})
LOCAL_SETTINGS_PATH = os.path.join(APP_DIR, ".local_settings.json")
DEVELOPER_CONTACT = APP_SETTINGS.get(
    "developer_contact", "569261093@qq.com; 15523182968"
)

# 常量定义
GUARDRAIL_BLOCK_MSG = "🚫 为了专注于学习，我无法回答与娱乐、游戏等无关的内容。请提问与知识、考试或学科相关的问题。"
CHAT_HISTORY_LIMIT = int(APP_SETTINGS.get("chat_history_limit", 8))
CHAT_HISTORY_LIMIT = max(0, min(CHAT_HISTORY_LIMIT, 20))


def resolve_path(path_value):
    """解析路径，支持相对路径和绝对路径"""
    if not path_value:
        return ""
    if os.path.isabs(path_value):
        return path_value
    return os.path.abspath(os.path.join(APP_DIR, path_value))


# 目录和文件前缀设置
SAVE_DIR = resolve_path(FILE_SETTINGS.get("save_dir", "./study_history"))
WRITING_FILE_PREFIX = FILE_SETTINGS.get("writing_file_prefix", "writing_session")

# Streamlit页面配置
st.set_page_config(
    page_title=APP_SETTINGS.get("title", "智学伴侣"),
    page_icon=APP_SETTINGS.get("page_icon", "🎓"),
    layout=APP_SETTINGS.get("layout", "wide"),
    initial_sidebar_state=APP_SETTINGS.get("sidebar_state", "expanded"),
)

# ---------------------------------------------------------
# 2. 基础工具函数
# ---------------------------------------------------------

def apply_custom_styles():
    """应用自定义CSS样式"""
    primary = UI_SETTINGS.get("primary_color", "#4F6EF7")
    secondary = UI_SETTINGS.get("secondary_color", "#FFB703")
    background = UI_SETTINGS.get("background_color", "#F6F8FF")
    card_bg = UI_SETTINGS.get("card_background", "#FFFFFF")
    text_color = UI_SETTINGS.get("text_color", "#1F2A44")
    font_family = UI_SETTINGS.get("font_family", "Segoe UI")

    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {background};
            color: {text_color};
            font-family: {font_family};
        }}
        div[data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #F3F6FF 0%, #E7EDFF 100%);
            border-right: 1px solid rgba(31, 42, 68, 0.06);
        }}
        .hero {{
            background: linear-gradient(120deg, {primary} 0%, #6AC3FF 60%, #9AE6B4 100%);
            padding: 26px 30px;
            border-radius: 18px;
            color: #ffffff;
            box-shadow: 0 12px 30px rgba(79, 110, 247, 0.25);
            margin-bottom: 20px;
        }}
        .hero-title {{
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 6px;
        }}
        .hero-subtitle {{
            font-size: 16px;
            opacity: 0.95;
        }}
        .hero-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.2);
            margin-right: 8px;
            font-size: 12px;
        }}
        div[data-testid="metric-container"] {{
            background: {card_bg};
            border-radius: 16px;
            padding: 14px 16px;
            border: 1px solid rgba(31, 42, 68, 0.08);
            box-shadow: 0 8px 20px rgba(31, 42, 68, 0.08);
        }}
        .card {{
            background: {card_bg};
            border-radius: 16px;
            padding: 16px 18px;
            border: 1px solid rgba(31, 42, 68, 0.08);
            box-shadow: 0 8px 20px rgba(31, 42, 68, 0.08);
        }}
        .tag {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            background: rgba(255, 183, 3, 0.15);
            color: {secondary};
            font-size: 12px;
            margin-right: 6px;
        }}
        /* 自定义滚动条 */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        ::-webkit-scrollbar-track {{
            background: #f1f1f1;
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb {{
            background: {primary};
            border-radius: 4px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #3d5ce0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_dir(path):
    """确保目录存在"""
    if path:
        os.makedirs(path, exist_ok=True)


def read_text_file(path):
    """读取文本文件"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""
    except Exception as e:
        st.warning(f"读取文件失败: {e}")
        return ""


def load_local_settings():
    """读取本地设置"""
    if not os.path.exists(LOCAL_SETTINGS_PATH):
        return {}
    try:
        with open(LOCAL_SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        st.warning(f"读取本地设置失败: {e}")
        return {}


def save_local_settings(settings):
    """保存本地设置"""
    try:
        current = load_local_settings()
        if not isinstance(current, dict):
            current = {}
        current.update(settings)
        with open(LOCAL_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"保存本地设置失败: {e}")
        return False


def clear_local_api_settings():
    """清除本地API设置"""
    try:
        current = load_local_settings()
        if "api_settings" in current:
            current.pop("api_settings", None)
            with open(LOCAL_SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"清除本地设置失败: {e}")
        return False


def parse_expire_at(expire_at_text):
    """解析授权码到期时间"""
    if not expire_at_text:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(expire_at_text, fmt)
        except ValueError:
            continue
    return None


def is_token_expired(expire_at_text):
    """判断授权码是否过期"""
    expire_dt = parse_expire_at(expire_at_text)
    if not expire_dt:
        return False
    return datetime.now() >= expire_dt


def build_runtime_api_config():
    """从本地配置构建API运行时配置"""
    api_cfg = CONFIG.get("api_settings", {})
    local_settings = load_local_settings()
    local_api = local_settings.get("api_settings", {}) if isinstance(local_settings, dict) else {}
    machine_code = get_machine_code()

    token = str(local_api.get("api_token", "") or "").strip()
    payload = decrypt_api_key(token, machine_code) if token else {}
    api_key = payload.get("api_key", "")
    payload_base_url = payload.get("base_url", "")
    payload_model = payload.get("model", "")
    expire_at = payload.get("expire_at", "")
    base_url = (payload_base_url or local_api.get("base_url") or api_cfg.get("base_url") or "").strip()
    model = (payload_model or local_api.get("model") or api_cfg.get("model") or "").strip()
    timeout = int(local_api.get("timeout") or api_cfg.get("timeout") or 60)
    stream = local_api.get("stream") if "stream" in local_api else api_cfg.get("stream", True)

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
        "stream": stream,
        "api_token": token,
        "expire_at": expire_at,
    }


def ensure_api_runtime():
    """确保API运行时配置可用"""
    if "api_runtime" not in st.session_state:
        st.session_state.api_runtime = build_runtime_api_config()


def get_subject_options():
    """获取学科选项列表"""
    subjects = list(SUBJECT_LIBRARY.keys())
    default_subject = SUBJECT_SETTINGS.get("default_subject", "全科")
    if default_subject and default_subject in subjects:
        subjects = [default_subject] + [s for s in subjects if s != default_subject]
    return subjects if subjects else [default_subject or "全科"]


def get_grade_options():
    """获取学段选项列表"""
    grades = SUBJECT_SETTINGS.get("grades", ["小学", "初中", "高中"])
    default_grade = SUBJECT_SETTINGS.get("default_grade", grades[0] if grades else "初中")
    if default_grade not in grades:
        grades = [default_grade] + grades
    return grades


def filter_topics(topics, keyword):
    """根据关键词过滤知识点"""
    if not keyword:
        return topics
    return [topic for topic in topics if keyword.lower() in topic.lower()]


def render_topic_tags(topics):
    """渲染知识点标签"""
    if not topics:
        return
    tags = " ".join([f'<span class="tag">{topic}</span>' for topic in topics])
    st.markdown(tags, unsafe_allow_html=True)


def list_history_files():
    """列出历史记录文件"""
    if not os.path.exists(SAVE_DIR):
        return []
    try:
        files = [
            os.path.join(SAVE_DIR, f)
            for f in os.listdir(SAVE_DIR)
            if f.lower().endswith(".md")
        ]
        files.sort(key=os.path.getmtime, reverse=True)
        return files
    except Exception as e:
        st.warning(f"读取历史记录失败: {e}")
        return []


def sanitize_filename(name):
    """净化文件名，移除非法字符"""
    if not name:
        return "未命名"
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name[:50] if len(name) > 50 else name


def build_chat_markdown(messages):
    """构建对话记录的Markdown格式"""
    lines = ["# 学习对话记录", ""]
    for msg in messages:
        role = "学生" if msg["role"] == "user" else "助手"
        lines.append(f"## {role}")
        lines.append(msg["content"])
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_context_messages(system_prompt, history, max_history):
    """构建上下文消息列表"""
    messages = [{"role": "system", "content": system_prompt}]
    if max_history <= 0:
        return messages
    filtered = [
        msg
        for msg in history
        if msg.get("role") in ("user", "assistant") and msg.get("content")
    ]
    if len(filtered) > max_history:
        filtered = filtered[-max_history:]
    messages.extend(filtered)
    return messages


def default_messages():
    """返回默认的欢迎消息"""
    return [
        {
            "role": "assistant",
            "content": "你好！我是你的智能学习助手，覆盖小学到中学教材知识（生物、英语、化学、物理等）。请在侧边栏选择学科与学段后提问。（例如：'初中物理讲解牛顿第二定律'）",
        }
    ]


def get_api_config():
    """获取API配置（从界面/本地设置加载）"""
    ensure_api_runtime()
    api_cfg = CONFIG.get("api_settings", {})
    runtime = st.session_state.get("api_runtime", {})

    base_url = (runtime.get("base_url") or api_cfg.get("base_url") or "").strip()
    model = (runtime.get("model") or api_cfg.get("model") or "").strip()
    timeout = int(runtime.get("timeout") or api_cfg.get("timeout") or 60)
    stream = runtime.get("stream") if "stream" in runtime else api_cfg.get("stream", True)

    return {
        "api_key": (runtime.get("api_key") or "").strip(),
        "base_url": base_url,
        "model": model,
        "timeout": timeout,
        "stream": stream,
        "expire_at": runtime.get("expire_at") or "",
    }


def is_api_ready():
    """检查API是否已配置"""
    api_cfg = get_api_config()
    api_key = api_cfg.get("api_key", "").strip()
    base_url = api_cfg.get("base_url", "").strip()
    model = api_cfg.get("model", "").strip()
    expire_at = api_cfg.get("expire_at", "").strip()
    if expire_at and is_token_expired(expire_at):
        return False
    return bool(api_key) and bool(base_url) and bool(model)


def get_api_client():
    """获取API客户端实例"""
    api_cfg = get_api_config()
    return OpenAI(
        api_key=api_cfg.get("api_key", ""),
        base_url=api_cfg.get("base_url") or None,
        timeout=api_cfg.get("timeout", 60),
    )


def check_guardrails(prompt):
    """检查输入是否违反安全围栏规则"""
    if not prompt:
        return True
    keywords = CONFIG.get("safety_guardrails", {}).get("blocked_keywords", [])
    prompt_lower = prompt.lower()
    for kw in keywords:
        if kw and kw.lower() in prompt_lower:
            return False
    return True


def is_safe_learning_input(*parts):
    """检查输入是否安全"""
    combined = " ".join(
        part.strip() for part in parts if isinstance(part, str) and part.strip()
    )
    return True if not combined else check_guardrails(combined)


def save_to_local(question, answer, scenario, temperature):
    """保存问答记录到本地"""
    ensure_dir(SAVE_DIR)
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_name = f"{FILE_SETTINGS.get('file_prefix', 'study_session')}_{date_str}.md"
    file_path = os.path.join(SAVE_DIR, file_name)
    timestamp = datetime.now().strftime("%H:%M:%S")

    content = f"""
## 🕒 时间: {timestamp}
**场景**: {scenario} (Temp: {temperature})

### ❓ 问题
{question}

### 💡回答
{answer}

---
"""
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)
        return file_path
    except Exception as e:
        st.warning(f"保存笔记失败: {e}")
        return ""


def save_writing_to_local(title, content, category):
    """保存作文到本地"""
    ensure_dir(SAVE_DIR)
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_name = f"{WRITING_FILE_PREFIX}_{date_str}.md"
    file_path = os.path.join(SAVE_DIR, file_name)
    timestamp = datetime.now().strftime("%H:%M:%S")
    safe_title = title if title else "未命名"

    entry = f"""
## 🕒 时间: {timestamp}
**类别**: {category}
**题目**: {safe_title}

### ✍️ 内容
{content}

---
"""
    try:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(entry)
        return file_path
    except Exception as e:
        st.warning(f"保存作文失败: {e}")
        return ""


# ---------------------------------------------------------
# 3. 提示词构建函数
# ---------------------------------------------------------

def build_system_prompt(selected_scenario, selected_subject, selected_grade):
    """构建系统提示词"""
    scope_statement = LEARNING_SCOPE.get("statement", "")
    scope_tip = LEARNING_SCOPE.get("tip", "")
    subject_tip = SUBJECT_GUIDANCE.get(selected_subject, "")
    return f"""
你是一名专业的中学全科辅导教师。你的目标是培养学生的自主探究能力。

请严格遵守以下回答规范：
1. **拒绝回答无关内容**：如果用户问及非学习内容，礼貌拒绝。
2. **格式要求**：回答必须包含以下三个Markdown章节，标题加粗，按顺序输出：
   - **🔍 1. 前序知识回顾**：简要说明理解该问题需要的基础概念。
   - **🧠 2. 核心知识解析与运用**：详细讲解知识点，并举例说明其在生活或后续高阶课程中的应用。
   - **📝 3. 考试考点预测**：基于历年考情，预测该知识点可能的出题方式或易错点。
3. **数学公式**：所有数学公式必须使用LaTeX格式，例如 $E=mc^2$ 或 $$\\frac{{a}}{{b}}$$。
4. **学段匹配**：用{selected_grade}学段可理解的表达，术语简明并给出必要解释。
5. **引导学习**：在第2部分开头给出1-2个引导性问题，再继续讲解。
6. **可选自测**：在三部分之后可追加 **✅ 4. 自测小题（可选）**，1-3题并给出简短答案。

当前学习场景：{selected_scenario}
当前学科：{selected_subject}，学段：{selected_grade}
学习覆盖：{scope_statement}
学习提示：{scope_tip}
学科提示：{subject_tip}
如问题超出所选学段，请给出衔接知识并标注更适合的年级范围。
"""


def build_plan_prompt(subject, days, focus, grade):
    """构建学习计划提示词"""
    return f"""
你是一名中学学习规划专家，请为学生制定一个 {days} 天的学习计划，适合{grade}学段。
要求：
1. 计划按天列出学习主题、任务与建议时间。
2. 每天包含"知识点学习 + 练习巩固 + 反思总结"。
3. 语言清晰、可执行，适合学生自主完成。

学科/章节：{subject}
学习目标：{focus}
"""


def build_practice_prompt(subject, difficulty, count, need_answer, grade):
    """构建练习题提示词"""
    answer_text = "附带答案解析" if need_answer else "只输出题目"
    return f"""
请围绕以下知识点生成 {count} 道{difficulty}难度的练习题，适合{grade}学段，{answer_text}。
输出格式：
- 题目编号
- 题目内容
- （如需）答案与解析

知识点：{subject}
"""


def build_card_prompt(topic, grade, style, subject):
    """构建知识点卡片提示词"""
    subject_text = f"学科：{subject}" if subject else ""
    return f"""
请生成一份"知识点卡片"，适合{grade}学生。
输出风格：{style}
要求：
1. 用清单或表格形式整理要点。
2. 给出常见误区和一条学习建议。

{subject_text}
知识点：{topic}
"""


def build_chinese_essay_prompt(data):
    """构建语文作文提示词"""
    lines = [
        f"适用学段：{data.get('grade', '高中')}",
        f"题目：{data.get('title') or '请自拟'}",
    ]

    if data.get("theme"):
        lines.append(f"主题：{data['theme']}")
    if data.get("essay_type") and data.get("essay_type") != "不限":
        lines.append(f"文体：{data['essay_type']}")
    if data.get("thesis"):
        lines.append(f"立意/论点：{data['thesis']}")
    if data.get("keywords"):
        lines.append(f"关键词/素材：{data['keywords']}")
    if data.get("word_count"):
        lines.append(f"目标字数：约{data['word_count']}字")
    if data.get("allusion_requirement"):
        lines.append(f"历史典故要求：{data['allusion_requirement']}")
    if data.get("extra_requirements"):
        lines.append(f"补充要求：{data['extra_requirements']}")

    outline_required = data.get("output_mode") in ("提纲", "提纲+范文")
    essay_required = data.get("output_mode") in ("范文", "提纲+范文")

    output_parts = []
    if outline_required:
        output_parts.append('输出"## 写作提纲"，用要点列出立意、结构与关键素材。')
    if essay_required:
        output_parts.append('输出"## 作文正文"，给出完整范文，结构清晰、语言自然。')

    output_instruction = "\n".join(output_parts) if output_parts else "输出完整作文正文。"

    return f"""
你是一名高考语文写作教研员，请根据以下信息生成作文。
要求：
1. 如果用户未提供题目，请自拟题目；若已提供，不要改写题目。
2. 论证严谨或叙事完整，注意段落层次与逻辑衔接。
3. 如指定历史典故，请自然融入，不要生硬堆砌。
4. 语言真实有文采，避免模板化口吻。

写作信息：
{chr(10).join(lines)}

输出要求：
1. 使用 Markdown。
2. {output_instruction}
"""


def build_english_essay_prompt(data):
    """构建英语作文提示词"""
    lines = [
        f"Grade: {data.get('grade', 'Senior High')}",
        f"Title: {data.get('title') or 'Please create one'}",
    ]

    if data.get("theme"):
        lines.append(f"Theme/Task: {data['theme']}")
    if data.get("essay_type") and data.get("essay_type") != "不限":
        lines.append(f"Essay type: {data['essay_type']}")
    if data.get("key_points"):
        lines.append(f"Key points: {data['key_points']}")
    if data.get("word_count"):
        lines.append(f"Word count: around {data['word_count']} words")
    if data.get("extra_requirements"):
        lines.append(f"Extra requirements: {data['extra_requirements']}")

    outline_required = data.get("output_mode") in ("提纲", "提纲+范文")
    essay_required = data.get("output_mode") in ("范文", "提纲+范文")

    output_parts = []
    if outline_required:
        output_parts.append('Provide a section titled "## Outline" with bullet points.')
    if essay_required:
        output_parts.append('Provide a section titled "## Essay" with the full text.')

    output_instruction = "\n".join(output_parts) if output_parts else "Provide the full essay text."

    return f"""
You are an English writing coach for the Gaokao. Generate an English essay based on the info below.
Requirements:
1. If no title is provided, create one; if provided, keep it unchanged.
2. Keep clear paragraphing and cohesive devices.
3. Use natural, accurate English; avoid overly generic phrasing.

Writing brief:
{chr(10).join(lines)}

Output requirements:
1. Use Markdown.
2. {output_instruction}
"""


def build_chinese_prediction_prompt(past_themes, count):
    """构建语文作文主题预测提示词"""
    themes_text = "\n".join([f"- {theme}" for theme in past_themes]) if past_themes else ""
    return f"""
你是一名高考作文命题研究员。请根据历年高考作文主题预测下一年可能考的主题。
要求：
1. 给出 {count} 个预测主题，每条包含：主题、可能命题角度、关键词。
2. 主题要贴合时代背景与学生生活，避免简单重复。
3. 使用 Markdown 列表输出，表达简洁但有理有据。

历年高考主题参考：
{themes_text}
"""


def build_english_prediction_prompt(past_prompts, count):
    """构建英语作文题目预测提示词"""
    prompts_text = "\n".join([f"- {prompt}" for prompt in past_prompts]) if past_prompts else ""
    return f"""
You are a Gaokao English writing examiner. Based on past writing prompts, predict possible topics for next year.
Requirements:
1. Provide {count} predicted prompts. Each item should include a topic, task type, and key points.
2. Keep it realistic for high school students and aligned with recent trends.
3. Use Markdown bullet lists. Output in English.

Past prompt references:
{prompts_text}
"""


# ---------------------------------------------------------
# 4. API调用函数
# ---------------------------------------------------------

def request_completion(messages, temperature, stream=False):
    """发送API请求获取完成结果"""
    client = get_api_client()
    api_cfg = get_api_config()
    return client.chat.completions.create(
        model=api_cfg.get("model") or "",
        messages=messages,
        temperature=temperature,
        stream=stream,
    )


def generate_text(system_prompt, user_prompt, temperature):
    """生成文本"""
    response = request_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        stream=False,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------
# 5. 处理函数
# ---------------------------------------------------------

def handle_chat_prompt(
    prompt,
    selected_scenario,
    selected_subject,
    selected_grade,
    current_temp,
    stream_enabled,
):
    """处理聊天提示"""
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if not is_safe_learning_input(prompt):
        st.session_state.messages.append({"role": "assistant", "content": GUARDRAIL_BLOCK_MSG})
        with st.chat_message("assistant"):
            st.error(GUARDRAIL_BLOCK_MSG)
        return

    system_prompt = build_system_prompt(
        selected_scenario, selected_subject, selected_grade
    )
    messages = build_context_messages(
        system_prompt, st.session_state.messages, CHAT_HISTORY_LIMIT
    )

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        response_ok = False

        try:
            if stream_enabled:
                stream = request_completion(
                    messages=messages,
                    temperature=current_temp,
                    stream=True,
                )

                for chunk in stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        full_response += delta.content
                        message_placeholder.markdown(full_response + "▌")

                message_placeholder.markdown(full_response)
                response_ok = True
            else:
                response = request_completion(
                    messages=messages,
                    temperature=current_temp,
                    stream=False,
                )
                full_response = response.choices[0].message.content
                message_placeholder.markdown(full_response)
                response_ok = True

        except Exception as e:
            st.error(f"❌ API 调用失败: {e}")
            full_response = "系统暂时无法连接到知识库，请检查网络或授权码设置。"

        st.session_state.messages.append({"role": "assistant", "content": full_response})

        if response_ok and full_response:
            try:
                saved_path = save_to_local(
                    prompt, full_response, selected_scenario, current_temp
                )
                if saved_path:
                    st.session_state["last_saved_path"] = saved_path
                    st.toast(f"✅ 笔记已自动保存", icon="💾")
            except Exception as e:
                st.warning(f"⚠️ 笔记保存失败: {e}")


# ---------------------------------------------------------
# 6. UI渲染函数
# ---------------------------------------------------------

def render_hero():
    """渲染顶部Hero区域"""
    title = APP_SETTINGS.get("title", "智学伴侣")
    subtitle = APP_SETTINGS.get("subtitle", "")
    version = APP_SETTINGS.get("version", "")
    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-title">{title}</div>
            <div class="hero-subtitle">{subtitle}</div>
            <div style="margin-top:12px;">
                <span class="hero-badge">版本 {version}</span>
                <span class="hero-badge">学习对话</span>
                <span class="hero-badge">作文写作</span>
                <span class="hero-badge">学习工具箱</span>
                <span class="hero-badge">成长档案</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_api_settings():
    """渲染API设置区域"""
    ensure_api_runtime()
    api_cfg = CONFIG.get("api_settings", {})
    runtime = st.session_state.get("api_runtime", {})
    local_settings = load_local_settings()
    local_api = local_settings.get("api_settings", {}) if isinstance(local_settings, dict) else {}
    machine_code = get_machine_code()

    with st.expander("🔑 API 设置", expanded=not is_api_ready()):
        st.text_input("本机机器码", value=machine_code, disabled=True)
        st.caption("向开发者申请授权码时请提供此机器码。")
        st.caption(f"开发者联系方式：{DEVELOPER_CONTACT}")

        if runtime.get("api_token") and not runtime.get("api_key"):
            st.warning("检测到本机授权码解密失败，请重新配置授权码。")
        if runtime.get("expire_at") and is_token_expired(runtime.get("expire_at")):
            st.error(f"授权码已过期（到期时间 {runtime.get('expire_at')}）。")
        if runtime.get("expire_at") and not is_token_expired(runtime.get("expire_at")):
            st.caption(f"授权有效期至：{runtime.get('expire_at')}")

        st.caption("向开发者获取授权码（需提供机器码）。")
        token_default = local_api.get("api_token", "") if isinstance(local_api, dict) else ""
        api_token_input = st.text_input(
            "授权码",
            type="password",
            value=token_default,
            key="api_token_input",
        ).strip()
        save_token = st.checkbox(
            "保存授权码到本机",
            value=True,
            key="api_token_save",
        )
        if st.button("验证并应用授权码", key="apply_api_token", use_container_width=True):
            if not api_token_input:
                st.error("请输入授权码。")
            else:
                payload = decrypt_api_key(api_token_input, machine_code)
                api_key = payload.get("api_key", "")
                payload_base_url = payload.get("base_url", "")
                payload_model = payload.get("model", "")
                payload_expire_at = payload.get("expire_at", "")
                if not api_key:
                    st.error("授权码无效或机器码不匹配。")
                else:
                    resolved_base_url = payload_base_url or runtime.get("base_url") or api_cfg.get("base_url", "")
                    resolved_model = payload_model or runtime.get("model") or api_cfg.get("model", "")
                    if payload_expire_at and is_token_expired(payload_expire_at):
                        st.error(f"授权码已过期（到期时间 {payload_expire_at}）。")
                        return
                    if not resolved_base_url or not resolved_model:
                        st.error("授权码缺少接口信息，请联系开发者重新生成。")
                    else:
                        runtime_update = {
                            "api_key": api_key,
                            "base_url": resolved_base_url,
                            "model": resolved_model,
                            "timeout": int(runtime.get("timeout") or api_cfg.get("timeout", 60)),
                            "stream": runtime.get("stream", api_cfg.get("stream", True)),
                            "api_token": api_token_input,
                            "expire_at": payload_expire_at,
                        }
                        st.session_state.api_runtime = runtime_update
                        if save_token:
                            save_local_settings(
                                {
                                    "api_settings": {
                                        "api_token": api_token_input,
                                        "base_url": runtime_update.get("base_url", ""),
                                        "model": runtime_update.get("model", ""),
                                        "expire_at": runtime_update.get("expire_at", ""),
                                        "timeout": runtime_update.get("timeout", 60),
                                        "stream": runtime_update.get("stream", True),
                                    }
                                }
                            )
                        st.success("✅ 授权码验证通过，已应用。")

        if st.button("🧹 清除本机API配置", key="clear_api_config"):
            if clear_local_api_settings():
                st.session_state.api_runtime = build_runtime_api_config()
                st.success("已清除本机API配置。")


def render_sidebar():
    """渲染侧边栏"""
    scenarios = CONFIG.get("scenarios", {})
    api_stream_default = get_api_config().get("stream", True)
    subject_options = get_subject_options()
    grade_options = get_grade_options()

    with st.sidebar:
        st.header("⚙️ 学习环境设置")

        default_subject = SUBJECT_SETTINGS.get(
            "default_subject", subject_options[0] if subject_options else "全科"
        )
        default_grade = SUBJECT_SETTINGS.get(
            "default_grade", grade_options[0] if grade_options else "初中"
        )

        selected_subject = st.selectbox(
            "学科", subject_options, 
            index=subject_options.index(default_subject) if default_subject in subject_options else 0
        )
        selected_grade = st.selectbox(
            "学段", grade_options, 
            index=grade_options.index(default_grade) if default_grade in grade_options else 0
        )

        if scenarios:
            scenario_keys = list(scenarios.keys())
            selected_scenario = st.radio("请选择当前学习任务：", scenario_keys)
            scenario_config = scenarios.get(selected_scenario, {})
            current_temp = scenario_config.get("temperature", 1.0)
        else:
            selected_scenario = "通用对话"
            current_temp = 1.0
            st.warning("未检测到场景配置，已启用默认模式。")

        stream_enabled = st.toggle("流式输出", value=api_stream_default)
        allow_custom = st.toggle("自定义温度", value=False)
        if allow_custom:
            current_temp = st.slider("温度", 0.0, 2.0, float(current_temp), 0.1)

        scenario_desc = scenario_config.get("description", "") if scenarios else ""
        st.info(
            f"""
            **当前模式**: {selected_scenario}
            **创造力指数 (Temperature)**: `{current_temp}`

            📝 **说明**: {scenario_desc}
            """
        )

        scope_statement = LEARNING_SCOPE.get("statement", "")
        scope_tip = LEARNING_SCOPE.get("tip", "")
        subject_tip = SUBJECT_GUIDANCE.get(selected_subject, "")
        if scope_statement:
            st.caption(f"📘 学习覆盖：{scope_statement}")
        if scope_tip:
            st.caption(f"💡 学习提示：{scope_tip}")
        if subject_tip:
            st.caption(f"🎯 学科提示：{subject_tip}")

        render_api_settings()

        st.markdown("---")
        st.caption(f"📂 笔记保存目录：{SAVE_DIR}")

        if st.button("🧹 清空对话记录"):
            st.session_state.messages = default_messages()
            st.rerun()

        # API状态显示
        if is_api_ready():
            st.success("✅ API 已配置")
        else:
            api_cfg = get_api_config()
            expire_at = api_cfg.get("expire_at", "")
            if expire_at and is_token_expired(expire_at):
                st.error("❌ 授权码已过期")
                st.info("请联系开发者重新获取授权码。")
            else:
                st.error("❌ API 未配置")
                st.info("请在侧边栏的“API 设置”中完成配置。")

        st.caption(f"👨‍💻 开发者：{DEVELOPER_CONTACT}")

    return selected_scenario, selected_subject, selected_grade, current_temp, stream_enabled


def render_chat_tab(
    selected_scenario, selected_subject, selected_grade, current_temp, stream_enabled
):
    """渲染学习对话标签页"""
    if "messages" not in st.session_state:
        st.session_state.messages = default_messages()

    history_files = list_history_files()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("累计笔记", len(history_files))
    col2.metric("当前学科", selected_subject)
    col3.metric("当前学段", selected_grade)
    col4.metric("温度", f"{current_temp:.1f}")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("请输入与学习相关的问题...")
    if prompt:
        if not is_api_ready():
            st.error("❌ API 未配置，无法生成回答。请在侧边栏“API 设置”中完成配置。")
        else:
            handle_chat_prompt(
                prompt,
                selected_scenario,
                selected_subject,
                selected_grade,
                current_temp,
                stream_enabled,
            )

    if len(st.session_state.messages) > 1:
        chat_md = build_chat_markdown(st.session_state.messages)
        file_name = f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        st.download_button("⬇️ 下载当前对话", chat_md, file_name=file_name)


def render_toolbox_tab(current_temp, selected_subject, selected_grade):
    """渲染学习工具箱标签页"""
    st.subheader("🧰 学习工具箱")
    st.caption("适合快速生成学习计划、练习题与知识卡片。")
    st.caption(f"当前学科/学段：{selected_subject} / {selected_grade}")

    if "toolbox_results" not in st.session_state:
        st.session_state.toolbox_results = {}

    if not is_api_ready():
        st.warning("⚠️ API 未配置，工具箱暂不可用。请在侧边栏“API 设置”中完成配置。")
        return

    toolbox_settings = CONFIG.get("toolbox_settings", {})
    grade_options = get_grade_options()
    default_grade = (
        selected_grade if selected_grade in grade_options else grade_options[0]
    )
    subject_default = "" if selected_subject == "全科" else selected_subject

    with st.expander("📅 学习计划生成", expanded=True):
        with st.form("plan_form", clear_on_submit=False):
            plan_grade = st.selectbox(
                "学段", grade_options, index=grade_options.index(default_grade) if default_grade in grade_options else 0, key="plan_grade"
            )
            subject = st.text_input(
                "学科/章节",
                placeholder="例如：初二物理·力与运动",
                value=subject_default,
                key="plan_subject",
            )
            days = st.slider(
                "计划天数",
                3,
                30,
                int(toolbox_settings.get("plan_days_default", 7)),
            )
            focus = st.text_area("学习目标", placeholder="例如：掌握牛顿运动定律并能完成典型题")
            submit_plan = st.form_submit_button("生成学习计划", use_container_width=True)

        if submit_plan:
            if not is_safe_learning_input(subject, focus):
                st.warning(GUARDRAIL_BLOCK_MSG)
            else:
                with st.spinner("正在生成学习计划..."):
                    try:
                        prompt = build_plan_prompt(subject, days, focus, plan_grade)
                        output = generate_text(
                            system_prompt="你是一名专业的学习规划导师。",
                            user_prompt=prompt,
                            temperature=current_temp,
                        )
                        st.session_state.toolbox_results["plan"] = output
                        st.success("✅ 学习计划生成成功！")
                    except Exception as e:
                        st.error(f"❌ 生成失败: {e}")

        plan_output = st.session_state.toolbox_results.get("plan")
        if plan_output:
            st.markdown(plan_output)

    with st.expander("🧩 练习题生成"):
        with st.form("practice_form", clear_on_submit=False):
            practice_grade = st.selectbox(
                "学段",
                grade_options,
                index=grade_options.index(default_grade) if default_grade in grade_options else 0,
                key="practice_grade",
            )
            subject = st.text_input(
                "知识点",
                placeholder="例如：一次函数图像",
                key="practice_subject",
                value=subject_default,
            )
            difficulty = st.selectbox("难度", ["基础", "提升", "挑战"])
            count = st.slider(
                "题目数量",
                1,
                10,
                int(toolbox_settings.get("practice_count_default", 5)),
            )
            need_answer = st.toggle("附带答案解析", value=True)
            submit_practice = st.form_submit_button("生成练习题", use_container_width=True)

        if submit_practice:
            if not is_safe_learning_input(subject):
                st.warning(GUARDRAIL_BLOCK_MSG)
            else:
                with st.spinner("正在生成练习题..."):
                    try:
                        prompt = build_practice_prompt(
                            subject, difficulty, count, need_answer, practice_grade
                        )
                        output = generate_text(
                            system_prompt="你是一名严谨的学科教师，擅长出题与解析。",
                            user_prompt=prompt,
                            temperature=current_temp,
                        )
                        st.session_state.toolbox_results["practice"] = output
                        st.success("✅ 练习题生成成功！")
                    except Exception as e:
                        st.error(f"❌ 生成失败: {e}")

        practice_output = st.session_state.toolbox_results.get("practice")
        if practice_output:
            st.markdown(practice_output)

    with st.expander("🧠 知识点卡片"):
        with st.form("card_form", clear_on_submit=False):
            topic = st.text_input(
                "知识点",
                placeholder="例如：细胞分裂",
                key="card_topic",
            )
            card_grades = grade_options + ["通用"]
            grade = st.selectbox(
                "学段",
                card_grades,
                index=card_grades.index(default_grade) if default_grade in card_grades else 0,
            )
            style = st.selectbox("输出风格", ["简洁要点", "对比表格", "思维导图描述"])
            submit_card = st.form_submit_button("生成卡片", use_container_width=True)

        if submit_card:
            if not is_safe_learning_input(topic):
                st.warning(GUARDRAIL_BLOCK_MSG)
            else:
                with st.spinner("正在生成知识点卡片..."):
                    try:
                        subject_hint = "" if selected_subject == "全科" else selected_subject
                        prompt = build_card_prompt(topic, grade, style, subject_hint)
                        output = generate_text(
                            system_prompt="你是一名资深教研员，擅长制作知识点卡片。",
                            user_prompt=prompt,
                            temperature=current_temp,
                        )
                        st.session_state.toolbox_results["card"] = output
                        st.success("✅ 知识点卡片生成成功！")
                    except Exception as e:
                        st.error(f"❌ 生成失败: {e}")

        card_output = st.session_state.toolbox_results.get("card")
        if card_output:
            st.markdown(card_output)


def render_writing_tab(current_temp, selected_grade):
    """渲染作文写作标签页"""
    st.subheader("✍️ 作文写作")
    st.caption("支持语文/英语作文生成与下一年考题预测。")

    if "writing_results" not in st.session_state:
        st.session_state.writing_results = {}

    if not is_api_ready():
        st.warning("⚠️ API 未配置，写作功能暂不可用。请在侧边栏“API 设置”中完成配置。")
        return

    grade_options = get_grade_options()
    default_grade = (
        selected_grade if selected_grade in grade_options else grade_options[0]
    )
    chinese_settings = WRITING_SETTINGS.get("chinese", {})
    english_settings = WRITING_SETTINGS.get("english", {})
    prediction_default = int(WRITING_SETTINGS.get("prediction_count_default", 3))
    prediction_default = max(1, min(prediction_default, 6))

    tabs = st.tabs(["语文作文", "英语作文"])

    with tabs[0]:
        with st.expander("📝 作文生成", expanded=True):
            with st.form("chinese_essay_form", clear_on_submit=False):
                cn_grade = st.selectbox(
                    "适用学段",
                    grade_options,
                    index=grade_options.index(default_grade) if default_grade in grade_options else 0,
                    key="cn_grade",
                )
                cn_title = st.text_input("题目（可选）", key="cn_title")
                cn_theme = st.text_input("主题（可选）", key="cn_theme")
                cn_types = ["不限"] + chinese_settings.get(
                    "types", ["议论文", "记叙文", "说明文", "散文", "应用文"]
                )
                cn_type = st.selectbox(
                    "文体（可选）", cn_types, index=0, key="cn_type"
                )
                cn_thesis = st.text_area(
                    "立意/论点（可选）", height=80, key="cn_thesis"
                )
                cn_keywords = st.text_area(
                    "关键词/素材（可选）", height=80, key="cn_keywords"
                )
                limit_cn_words = st.toggle(
                    "限制字数（可选）", value=True, key="cn_limit_words"
                )
                cn_word_count = None
                if limit_cn_words:
                    cn_default_count = int(chinese_settings.get("default_word_count", 800))
                    cn_word_count = st.number_input(
                        "目标字数",
                        min_value=300,
                        max_value=1200,
                        value=cn_default_count,
                        step=50,
                        key="cn_word_count",
                    )

                cn_allusion_option = st.selectbox(
                    "历史典故（可选）",
                    ["不使用", "自动推荐", "从素材库选择", "自定义"],
                    key="cn_allusion_option",
                )
                cn_allusion_requirement = ""
                if cn_allusion_option == "从素材库选择":
                    cn_library = chinese_settings.get("historical_allusions", [])
                    cn_selected = st.multiselect(
                        "选择典故", cn_library, key="cn_allusion_select"
                    )
                    cn_allusion_requirement = (
                        "、".join(cn_selected)
                        if cn_selected
                        else "自动推荐并融入1-2个相关历史典故"
                    )
                elif cn_allusion_option == "自定义":
                    cn_custom = st.text_input(
                        "自定义历史典故", key="cn_allusion_custom"
                    ).strip()
                    cn_allusion_requirement = (
                        cn_custom if cn_custom else "自动推荐并融入1-2个相关历史典故"
                    )
                elif cn_allusion_option == "自动推荐":
                    cn_allusion_requirement = "自动推荐并融入1-2个相关历史典故"
                else:
                    cn_allusion_requirement = "不强制"

                cn_extra = st.text_area(
                    "补充要求（可选）", height=80, key="cn_extra"
                )
                cn_output_mode = st.selectbox(
                    "输出形式", ["范文", "提纲", "提纲+范文"], index=0, key="cn_output_mode"
                )
                submit_cn = st.form_submit_button("生成语文作文", use_container_width=True)

            if submit_cn:
                if not is_safe_learning_input(
                    cn_title, cn_theme, cn_thesis, cn_keywords, cn_extra
                ):
                    st.warning(GUARDRAIL_BLOCK_MSG)
                else:
                    with st.spinner("正在生成作文..."):
                        data = {
                            "grade": cn_grade,
                            "title": cn_title.strip(),
                            "theme": cn_theme.strip(),
                            "essay_type": cn_type,
                            "thesis": cn_thesis.strip(),
                            "keywords": cn_keywords.strip(),
                            "word_count": cn_word_count,
                            "allusion_requirement": cn_allusion_requirement,
                            "extra_requirements": cn_extra.strip(),
                            "output_mode": cn_output_mode,
                        }
                        try:
                            output = generate_text(
                                system_prompt="你是一名高考语文写作教研员。",
                                user_prompt=build_chinese_essay_prompt(data),
                                temperature=current_temp,
                            )
                            st.session_state.writing_results["chinese_essay"] = output
                            st.session_state.writing_results["chinese_essay_title"] = cn_title.strip()
                            st.success("✅ 作文生成成功！")
                        except Exception as e:
                            st.error(f"❌ 生成失败: {e}")

            cn_output = st.session_state.writing_results.get("chinese_essay")
            if cn_output:
                cn_saved_title = st.session_state.writing_results.get(
                    "chinese_essay_title", cn_title
                )
                st.markdown(cn_output)
                cn_file_title = (
                    sanitize_filename(cn_saved_title) if cn_saved_title else "语文作文"
                )
                cn_file_name = (
                    f"{cn_file_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                )
                st.download_button(
                    "⬇️ 下载作文", cn_output, file_name=cn_file_name, key="cn_download"
                )
                if st.button("💾 保存到学习档案", key="cn_save"):
                    saved_path = save_writing_to_local(
                        cn_saved_title, cn_output, "语文作文"
                    )
                    st.success(f"✅ 已保存至 {saved_path}")

        with st.expander("📈 下一年高考主题预测"):
            cn_past_themes = chinese_settings.get("past_themes", [])
            if cn_past_themes:
                st.caption("历年高考主题（参考）")
                st.markdown("\n".join([f"- {theme}" for theme in cn_past_themes]))
            else:
                st.info("未配置历年主题，可在 config.yaml 中补充。")

            with st.form("chinese_predict_form", clear_on_submit=False):
                cn_count = st.slider(
                    "预测数量", 1, 6, prediction_default, key="cn_predict_count"
                )
                submit_cn_predict = st.form_submit_button("生成预测", use_container_width=True)

            if submit_cn_predict:
                if not cn_past_themes:
                    st.warning("暂无历年主题数据，无法生成预测。")
                else:
                    with st.spinner("正在预测..."):
                        try:
                            predict_output = generate_text(
                                system_prompt="你是一名高考作文命题研究员。",
                                user_prompt=build_chinese_prediction_prompt(
                                    cn_past_themes, cn_count
                                ),
                                temperature=current_temp,
                            )
                            st.session_state.writing_results["chinese_predict"] = predict_output
                            st.success("✅ 预测完成！")
                        except Exception as e:
                            st.error(f"❌ 生成失败: {e}")

            cn_predict = st.session_state.writing_results.get("chinese_predict")
            if cn_predict:
                st.markdown(cn_predict)

    with tabs[1]:
        with st.expander("📝 作文生成（英语）", expanded=True):
            with st.form("english_essay_form", clear_on_submit=False):
                en_grade = st.selectbox(
                    "适用学段",
                    grade_options,
                    index=grade_options.index(default_grade) if default_grade in grade_options else 0,
                    key="en_grade",
                )
                en_title = st.text_input("题目（可选）", key="en_title")
                en_theme = st.text_input("主题/任务（可选）", key="en_theme")
                en_types = ["不限"] + english_settings.get(
                    "types",
                    ["应用文", "议论文", "说明文", "记叙文", "读后续写", "概要写作", "演讲稿"],
                )
                en_type = st.selectbox(
                    "文体（可选）", en_types, index=0, key="en_type"
                )
                en_points = st.text_area(
                    "要点/信息（可选）", height=80, key="en_points"
                )
                limit_en_words = st.toggle(
                    "限制字数（可选）", value=True, key="en_limit_words"
                )
                en_word_count = None
                if limit_en_words:
                    en_default_count = int(english_settings.get("default_word_count", 120))
                    en_word_count = st.number_input(
                        "目标字数",
                        min_value=60,
                        max_value=200,
                        value=en_default_count,
                        step=10,
                        key="en_word_count",
                    )
                en_extra = st.text_area(
                    "补充要求（可选）", height=80, key="en_extra"
                )
                en_output_mode = st.selectbox(
                    "输出形式", ["范文", "提纲", "提纲+范文"], index=0, key="en_output_mode"
                )
                submit_en = st.form_submit_button("生成英语作文", use_container_width=True)

            if submit_en:
                if not is_safe_learning_input(en_title, en_theme, en_points, en_extra):
                    st.warning(GUARDRAIL_BLOCK_MSG)
                else:
                    with st.spinner("正在生成作文..."):
                        data = {
                            "grade": en_grade,
                            "title": en_title.strip(),
                            "theme": en_theme.strip(),
                            "essay_type": en_type,
                            "key_points": en_points.strip(),
                            "word_count": en_word_count,
                            "extra_requirements": en_extra.strip(),
                            "output_mode": en_output_mode,
                        }
                        try:
                            output = generate_text(
                                system_prompt="You are an experienced Gaokao English writing coach.",
                                user_prompt=build_english_essay_prompt(data),
                                temperature=current_temp,
                            )
                            st.session_state.writing_results["english_essay"] = output
                            st.session_state.writing_results["english_essay_title"] = en_title.strip()
                            st.success("✅ 作文生成成功！")
                        except Exception as e:
                            st.error(f"❌ 生成失败: {e}")

            en_output = st.session_state.writing_results.get("english_essay")
            if en_output:
                en_saved_title = st.session_state.writing_results.get(
                    "english_essay_title", en_title
                )
                st.markdown(en_output)
                en_file_title = (
                    sanitize_filename(en_saved_title) if en_saved_title else "English_Essay"
                )
                en_file_name = (
                    f"{en_file_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                )
                st.download_button(
                    "⬇️ 下载作文", en_output, file_name=en_file_name, key="en_download"
                )
                if st.button("💾 保存到学习档案", key="en_save"):
                    saved_path = save_writing_to_local(
                        en_saved_title, en_output, "英语作文"
                    )
                    st.success(f"✅ 已保存至 {saved_path}")

        with st.expander("📈 下一年考题预测（英语）"):
            en_past_prompts = english_settings.get("past_prompts", [])
            if en_past_prompts:
                st.caption("Past prompt references")
                st.markdown("\n".join([f"- {prompt}" for prompt in en_past_prompts]))
            else:
                st.info("No past prompts configured. Add them in config.yaml.")

            with st.form("english_predict_form", clear_on_submit=False):
                en_count = st.slider(
                    "预测数量", 1, 6, prediction_default, key="en_predict_count"
                )
                submit_en_predict = st.form_submit_button("生成预测", use_container_width=True)

            if submit_en_predict:
                if not en_past_prompts:
                    st.warning("暂无历年写作题目数据，无法生成预测。")
                else:
                    with st.spinner("正在预测..."):
                        try:
                            predict_output = generate_text(
                                system_prompt="You are a Gaokao English writing examiner.",
                                user_prompt=build_english_prediction_prompt(
                                    en_past_prompts, en_count
                                ),
                                temperature=current_temp,
                            )
                            st.session_state.writing_results["english_predict"] = predict_output
                            st.success("✅ 预测完成！")
                        except Exception as e:
                            st.error(f"❌ 生成失败: {e}")

            en_predict = st.session_state.writing_results.get("english_predict")
            if en_predict:
                st.markdown(en_predict)


def render_subject_tab(selected_subject, selected_grade):
    """渲染学科导航标签页"""
    st.subheader("📖 学科导航")
    st.caption("覆盖小学到中学主要教材知识点，可按学科与学段浏览。")

    if not SUBJECT_LIBRARY:
        st.info("未配置学科知识库，请在 config.yaml 中补充。")
        return

    subject_options = ["全部"] + list(SUBJECT_LIBRARY.keys())
    grade_options = ["全部"] + get_grade_options()

    subject_index = subject_options.index(selected_subject) if selected_subject in subject_options else 0
    grade_index = grade_options.index(selected_grade) if selected_grade in grade_options else 0

    col1, col2 = st.columns(2)
    with col1:
        subject_filter = st.selectbox("学科筛选", subject_options, index=subject_index)
    with col2:
        grade_filter = st.selectbox("学段筛选", grade_options, index=grade_index)

    search_keyword = st.text_input("搜索知识点", placeholder="例如：电路、时态、细胞").strip()

    matched = False
    for subject, stages in SUBJECT_LIBRARY.items():
        if subject_filter != "全部" and subject != subject_filter:
            continue

        with st.expander(f"📘 {subject}", expanded=(subject == selected_subject)):
            for stage, topics in stages.items():
                if grade_filter != "全部" and stage != grade_filter:
                    continue
                filtered_topics = filter_topics(topics, search_keyword)
                if not filtered_topics:
                    continue
                matched = True
                st.markdown(f"**{stage}**")
                render_topic_tags(filtered_topics)

    if search_keyword and not matched:
        st.warning("未匹配到相关知识点，可尝试更换关键词或调整筛选条件。")


def render_history_tab():
    """渲染学习档案标签页"""
    st.subheader("📚 学习档案")
    st.caption("支持查看历史问答记录与下载。")

    files = list_history_files()
    if not files:
        st.info("暂无历史记录，完成一次对话后会自动保存。")
        return

    file_names = [os.path.basename(f) for f in files]
    selected_file = st.selectbox("选择记录文件", file_names)
    selected_path = files[file_names.index(selected_file)]

    content = read_text_file(selected_path)
    if content:
        st.markdown(content)
        st.download_button("⬇️ 下载记录", content, file_name=selected_file)
    else:
        st.warning("文件内容为空或读取失败。")


# ---------------------------------------------------------
# 7. 主函数
# ---------------------------------------------------------

def main():
    """主函数"""
    apply_custom_styles()
    render_hero()

    (
        selected_scenario,
        selected_subject,
        selected_grade,
        current_temp,
        stream_enabled,
    ) = render_sidebar()

    tabs = st.tabs(
        ["💬 学习对话", "📖 学科导航", "🧰 学习工具箱", "✍️ 作文写作", "📚 学习档案"]
    )
    with tabs[0]:
        render_chat_tab(
            selected_scenario,
            selected_subject,
            selected_grade,
            current_temp,
            stream_enabled,
        )
    with tabs[1]:
        render_subject_tab(selected_subject, selected_grade)
    with tabs[2]:
        render_toolbox_tab(current_temp, selected_subject, selected_grade)
    with tabs[3]:
        render_writing_tab(current_temp, selected_grade)
    with tabs[4]:
        render_history_tab()


if __name__ == "__main__":
    main()
