import streamlit as st
import pandas as pd
import json
import os
import plotly.graph_objects as go
from openai import OpenAI

# ----------------- 页面配置 -----------------
st.set_page_config(
    page_title="GTM & 用户体验智能诊断工作台 (DeepSeek版)",
    page_icon="🚀",
    layout="wide"
)

# ----------------- 侧边栏配置 -----------------
with st.sidebar:
    st.header("⚙️ DeepSeek 配置")
    api_key = st.text_input(
        "DeepSeek API Key", 
        value=os.environ.get("DEEPSEEK_API_KEY", ""), 
        type="password", 
        help="请填入在 DeepSeek 平台获取的 sk-xxx 密钥"
    )
    selected_model = st.selectbox(
        "选择模型", 
        ["deepseek-chat", "deepseek-reasoner"], 
        index=0,
        help="deepseek-chat 为日常极速版；deepseek-reasoner 为深度推理版"
    )
    st.divider()

# 初始化 DeepSeek 客户端
if api_key:
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"  # 接入 DeepSeek 服务器
    )
else:
    client = None
    st.sidebar.warning("👈 请先在左侧填入 DeepSeek API Key")

# ----------------- 核心功能函数 -----------------
def calculate_predicted_ltv(traffic_volume, avg_duration_sec, base_arpu=100):
    """定量：根据流量与停留时长加权估算 LTV 基准"""
    duration_weight = min(avg_duration_sec / 180.0, 2.0)
    estimated_cvr = 0.05 * duration_weight
    predicted_ltv = base_arpu * (1 + duration_weight)
    return {
        "estimated_cvr": f"{estimated_cvr * 100:.2f}%",
        "predicted_ltv_tier": "High" if predicted_ltv > 180 else "Medium",
        "benchmark_ltv": round(predicted_ltv, 2)
    }

def extract_voc_insights(raw_feedback_list, model="deepseek-chat"):
    """定性：结构化提炼用户原声"""
    prompt = f"""
    你是一个资深产品体验专家。请对以下测试用户原声进行分析，提取关键痛点、核心阻力以及惊艳时刻(Aha Moment)。
    必须输出为标准 JSON 格式，包含三个数组字段: 
    - "pain_points" (痛点列表)
    - "friction_points" (流失阻力列表)
    - "aha_moments" (惊艳时刻列表)

    用户原声内容:
    {json.dumps(raw_feedback_list, ensure_ascii=False)}
    """
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"} if model == "deepseek-chat" else None,
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    return json.loads(content)

def generate_gtm_strategy(benchmark_data, funnel_drop_stage, voc_insights, model="deepseek-chat"):
    """赋能：交叉归因并输出 GTM 优化策略"""
    prompt = f"""
    你是一名负责新产品孵化的 GTM（Go-To-Market）增长总监。请结合以下全链路输入生成跨部门协同方案：
    
    1. 竞品及LTV基准: {benchmark_data}
    2. 当前测试漏斗最大流失节点: {funnel_drop_stage}
    3. 测试用户VOC提取: {voc_insights}

    请使用结构化 Markdown 输出以下 4 个模块：
    ### 一、 流失根因归因与典型案例萃取
    ### 二、 产研迭代优先级 (Product Roadmap P0/P1)
    ### 三、 市场投放与文案调整 (Messaging/Copywriting)
    ### 四、 销售/社群高转化触达话术 (Sales Playbook)
    """
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ----------------- UI 界面搭建 -----------------
st.title("🚀 GTM & 用户体验全链路智能复盘工作台")

col_left, col_right = st.columns([1, 1], gap="large")

with col_left:
    st.subheader("1. 定量指标与转化漏斗")
    with st.expander("📊 竞品及基准指标设置", expanded=True):
        c1, c2, c3 = st.columns(3)
        traffic = c1.number_input("月度测试流量", value=50000, step=1000)
        duration = c2.number_input("平均停留时长(秒)", value=240, step=10)
        arpu = c3.number_input("基准客单价", value=100, step=10)
        benchmark_res = calculate_predicted_ltv(traffic, duration, arpu)
        st.info(f"预估转化率：**{benchmark_res['estimated_cvr']}** ｜ 预测 LTV：**¥{benchmark_res['benchmark_ltv']}**")

    with st.expander("🔻 转化漏斗数据", expanded=True):
        f1 = st.number_input("1. 访问注册人数", value=10000)
        f2 = st.number_input("2. 新手引导完成人数", value=6200)
        f3 = st.number_input("3. 核心功能体验人数", value=3600)
        f4 = st.number_input("4. 付费转化人数", value=450)

        fig = go.Figure(go.Funnel(
            y=["访问注册", "新手引导", "核心功能", "付费转化"],
            x=[f1, f2, f3, f4],
            textinfo="value+percent initial"
        ))
        fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=220)
        st.plotly_chart(fig, use_container_width=True)

        drop_node = st.selectbox(
            "选择需攻坚的最大流失节点：",
            [
                "新手引导 -> 首次体验核心功能（流失率约 42%）", 
                "访问落地页 -> 注册转化", 
                "核心功能体验 -> 付费转化"
            ]
        )

with col_right:
    st.subheader("2. 定性用户原声 (VOC) 录入")
    tab_upload, tab_manual = st.tabs(["📁 上传 CSV 文件", "✍️ 直接粘贴原声"])
    feedbacks_to_process = []
    
    with tab_upload:
        file = st.file_uploader("上传含测试用户反馈的 CSV 表格", type=["csv"])
        if file:
            df = pd.read_csv(file)
            col = st.selectbox("选择反馈文本所在的列：", df.columns)
            feedbacks_to_process = df[col].dropna().astype(str).tolist()
            st.success(f"已成功加载 {len(feedbacks_to_process)} 条原声反馈！")

    with tab_manual:
        default_txt = "注册完了不知道下一步该点哪里，找半天核心功能。\n第一次生成报告的时候感觉很惊艳，但导入数据时报错两次。\n如果能一键同步竞品数据就好了，手动填太慢。"
        txt = st.text_area("每行一条原声：", value=default_txt, height=150)
        if txt.strip() and not feedbacks_to_process:
            feedbacks_to_process = [l.strip() for l in txt.split("\n") if l.strip()]

    run_btn = st.button("⚡ 开始全链路分析并生成 GTM 策略", type="primary", use_container_width=True)

# ----------------- 生成交付结果 -----------------
if run_btn:
    if not client:
        st.error("请先在左侧侧边栏填入 DeepSeek API Key！")
    elif not feedbacks_to_process:
        st.error("请提供至少一条用户原声！")
    else:
        with st.spinner("🤖 DeepSeek 正在交叉分析数据并生成策略报告..."):
            try:
                voc_res = extract_voc_insights(feedbacks_to_process, model=selected_model)
                gtm_res = generate_gtm_strategy(benchmark_res, drop_node, voc_res, model=selected_model)

                st.divider()
                st.subheader("📌 结构化 VOC 提炼卡片")
                v1, v2, v3 = st.columns(3)
                v1.error("**❌ 核心痛点 (Pain Points)**\n\n" + "\n\n".join([f"- {i}" for i in voc_res.get("pain_points", [])]))
                v2.warning("**⚠️ 流失阻力 (Friction Points)**\n\n" + "\n\n".join([f"- {i}" for i in voc_res.get("friction_points", [])]))
                v3.success("**✨ 惊艳时刻 (Aha Moments)**\n\n" + "\n\n".join([f"- {i}" for i in voc_res.get("aha_moments", [])]))

                st.divider()
                st.markdown(gtm_res)
                st.download_button(
                    label="📥 一键下载完整复盘报告 (.md)", 
                    data=gtm_res, 
                    file_name="GTM_Optimization_Report.md",
                    mime="text/markdown"
                )
            except Exception as e:
                st.error(f"处理失败，错误信息: {str(e)}")
