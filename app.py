# -*- coding: utf-8 -*-
"""
BiliDaka / 分P研习录
B站多视频分P学习进度批量打卡工具（Streamlit Web App）

启动方式:  streamlit run app.py
依赖库:    streamlit, pandas, requests
数据文件:  同目录下 bili_checklist.csv（自动创建/加载）
"""

import re
import streamlit as st
import pandas as pd
import requests

# ==================== 常量 ====================
CSV_PATH = "bili_checklist.csv"
API_URL = "http://api.bilibili.com/x/web-interface/view"
# B站API需要带浏览器UA，否则可能被拒绝
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}
# 标准BV号：BV + 10位大小写字母数字
BV_PATTERN = re.compile(r"(BV[0-9A-Za-z]{10})")

# 表格列顺序（必须严格遵循）
COLUMN_ORDER = ["视频标题", "BV号", "分P序号", "分P标题", "是否看完", "理解程度", "刷了几遍", "备注"]
UNDERSTAND_OPTS = ["懂", "半懂", "不懂"]


# ==================== 数据层 ====================
def empty_df():
    """构造带正确列名与类型的空表。"""
    return pd.DataFrame(
        {
            "视频标题": pd.Series(dtype="object"),
            "BV号": pd.Series(dtype="object"),
            "分P序号": pd.Series(dtype="int64"),
            "分P标题": pd.Series(dtype="object"),
            "是否看完": pd.Series(dtype="bool"),
            "理解程度": pd.Series(dtype="object"),
            "刷了几遍": pd.Series(dtype="int64"),
            "备注": pd.Series(dtype="object"),
        }
    )[COLUMN_ORDER]


def normalize_df(df):
    """修正/补齐列与类型，兼容历史或损坏数据，确保不崩溃。"""
    # 补齐缺失列
    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMN_ORDER].copy()

    # 视频标题 / BV号 / 分P标题 / 备注：字符串
    for col in ["视频标题", "BV号", "分P标题", "备注"]:
        df[col] = df[col].fillna("").astype(str)

    # 分P序号：整数
    df["分P序号"] = (
        pd.to_numeric(df["分P序号"], errors="coerce").fillna(0).astype("int64")
    )

    # 是否看完：布尔（兼容 CSV 中 True/False/1/0/是/否 等写法）
    df["是否看完"] = (
        df["是否看完"]
        .astype(str)
        .str.strip()
        .str.lower()
        .map({"true": True, "false": False, "1": True, "0": False,
              "是": True, "否": False})
        .fillna(False)
        .astype(bool)
    )

    # 理解程度：限定在三个选项内，非法值兜底为“不懂”
    df["理解程度"] = df["理解程度"].where(df["理解程度"].isin(UNDERSTAND_OPTS), "不懂")
    df["理解程度"] = df["理解程度"].fillna("不懂").astype(str)

    # 刷了几遍：非负整数
    times = pd.to_numeric(df["刷了几遍"], errors="coerce").fillna(0).astype("int64")
    df["刷了几遍"] = times.clip(lower=0)

    return df


def load_data():
    """启动时加载 CSV；文件不存在返回空表；文件损坏则警告并返回空表。"""
    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    except FileNotFoundError:
        return empty_df()
    except pd.errors.EmptyDataError:
        return empty_df()
    except Exception as e:
        st.warning(f"数据文件 {CSV_PATH} 损坏或无法读取，已按空表启动。错误信息：{e}")
        return empty_df()
    return normalize_df(df)


def save_data(df):
    """覆盖保存到 CSV（utf-8-sig 保证 Excel 打开中文不乱码）。"""
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")


# ==================== B站API ====================
def extract_bvid(text):
    """从粘贴的链接或裸 BV 号中提取标准 BV 号。"""
    if not text:
        return None
    m = BV_PATTERN.search(text.strip())
    return m.group(1) if m else None


def fetch_video_info(bvid):
    """调用B站 web-interface/view 接口，返回 JSON dict。"""
    resp = requests.get(
        API_URL,
        params={"bvid": bvid},
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ==================== 页面初始化 ====================
st.set_page_config(
    page_title="BiliDaka · 分P研习录",
    page_icon="📺",
    layout="wide",
)

# 限制主内容区最大宽度并居中，避免宽屏下内容过散
st.markdown(
    """
    <style>
        .block-container {
            max-width: 1150px;
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if "df" not in st.session_state:
    st.session_state.df = load_data()


# ==================== 侧边栏：添加区 ====================
with st.sidebar:
    st.header("➕ 添加视频")
    bv_input = st.text_input(
        "粘贴B站视频链接或BV号",
        placeholder="https://www.bilibili.com/video/BV1XW4y1Z789",
        label_visibility="visible",
    )
    add_clicked = st.button("抓取并添加", width="stretch", type="primary")

    if add_clicked:
        bvid = extract_bvid(bv_input)
        if not bvid:
            st.error("无法识别 BV 号，请粘贴正确的视频链接或直接输入 BV 号。")
        elif bvid in st.session_state.df["BV号"].values:
            st.warning(f"该视频已存在（{bvid}），不会重复添加。")
        else:
            try:
                with st.spinner("正在抓取分P信息…"):
                    info = fetch_video_info(bvid)
            except requests.exceptions.Timeout:
                st.error("请求 B站API 超时，请检查网络后重试。")
            except requests.exceptions.ConnectionError:
                st.error("网络连接失败，请检查网络设置后重试。")
            except requests.exceptions.RequestException as e:
                st.error(f"网络请求失败：{e}")
            except ValueError:
                st.error("B站API 返回了无法解析的内容，请稍后重试。")
            except Exception as e:
                st.error(f"发生未知错误：{e}")
            else:
                code = info.get("code", -1)
                if code != 0:
                    msg = info.get("message", "未知错误")
                    st.error(
                        f"B站API 返回错误（code={code}）：{msg}。"
                        "可能是 BV 号无效，或视频为私密/已删除。"
                    )
                else:
                    data = info.get("data") or {}
                    title = data.get("title", "（无标题）")
                    pages = data.get("pages") or []
                    if not pages:
                        st.error("该视频没有分P信息，无法添加。")
                    else:
                        new_rows = [
                            {
                                "视频标题": title,
                                "BV号": bvid,
                                "分P序号": int(p.get("page", idx + 1)),
                                "分P标题": p.get("part") or f"P{idx + 1}",
                                "是否看完": False,
                                "理解程度": "不懂",
                                "刷了几遍": 0,
                                "备注": "",
                            }
                            for idx, p in enumerate(pages)
                        ]
                        merged = pd.concat(
                            [st.session_state.df, pd.DataFrame(new_rows)],
                            ignore_index=True,
                        )
                        st.session_state.df = normalize_df(merged)
                        # 数据变化，清除所有分表 widget 状态，避免与新数据冲突
                        for k in list(st.session_state.keys()):
                            if k.startswith("editor_"):
                                del st.session_state[k]
                        st.success(f"已添加《{title}》，共 {len(new_rows)} 个分P。")
                        st.rerun()

    st.divider()
    cur_df = st.session_state.df
    video_count = cur_df["BV号"].nunique() if not cur_df.empty else 0
    part_count = len(cur_df)
    st.caption(f"当前共管理 **{video_count}** 个视频，**{part_count}** 个分P")


# ==================== 主区域 ====================
st.title("📺 BiliDaka · 分P研习录")
st.caption("批量管理 B站多视频分P学习进度，勾选即打卡，数据本地保存为 CSV。")

# 指标看板占位（位于表格上方，拿到 data_editor 返回的最新数据后回填）
metrics_placeholder = st.empty()

st.divider()

# ---------- 打卡表格（按视频分表） ----------
st.subheader("📋 打卡表格")

cur_df = st.session_state.df
if cur_df.empty:
    st.info("还没有任何视频，请在左侧侧边栏粘贴 B站链接或 BV 号，点击“抓取并添加”开始。")

# 子表中不显示“视频标题/BV号”（已在卡片标题区展示），只保留分P相关列
SUB_COLUMNS = ["分P序号", "分P标题", "是否看完", "理解程度", "刷了几遍", "备注"]

edited_groups = []
# sort=False 保持视频添加顺序


def apply_batch(bvid, p_start, p_end, watched, understand, times):
    """对指定 BV号、指定分P序号范围批量更新字段。
    watched: "不修改"/"已看"/"未看"；understand: "不修改"/"懂"/"半懂"/"不懂"；
    times: -1 表示不修改，>=0 表示设置刷数。"""
    df = st.session_state.df
    mask = (
        (df["BV号"] == bvid)
        & (df["分P序号"] >= int(p_start))
        & (df["分P序号"] <= int(p_end))
    )
    if not mask.any():
        st.warning("选定范围内没有分P，未做修改。")
        return
    if watched == "已看":
        df.loc[mask, "是否看完"] = True
    elif watched == "未看":
        df.loc[mask, "是否看完"] = False
    if understand != "不修改":
        df.loc[mask, "理解程度"] = understand
    if times >= 0:
        df.loc[mask, "刷了几遍"] = int(times)
    st.session_state.df = normalize_df(df)
    # 数据被外部修改，清除该分表 widget 状态，下次 rerun 用新数据重建
    st.session_state.pop(f"editor_{bvid}", None)
    st.rerun()


for bvid, group in cur_df.groupby("BV号", sort=False):
    video_title = group["视频标题"].iloc[0] or "（无标题）"
    part_total = len(group)
    part_done = int(group["是否看完"].sum())
    part_rate = (part_done / part_total) if part_total else 0.0

    with st.container(border=True):
        # 卡片标题行：视频名 + 进度
        head_col1, head_col2 = st.columns([4, 1])
        with head_col1:
            st.markdown(f"#### 🎬 {video_title}")
        with head_col2:
            st.metric(
                "本视频进度",
                f"{part_done}/{part_total}",
                f"{part_rate * 100:.0f}%",
            )
        st.caption(f"`{bvid}`")
        st.progress(part_rate)

        # ---- 批量操作 ----
        qc1, qc2, qc3 = st.columns([1, 1, 2])
        with qc1:
            if st.button("✅ 全部已看", key=f"allwatch_{bvid}", width="stretch"):
                apply_batch(bvid, 1, part_total, "已看", "不修改", -1)
        with qc2:
            if st.button("↩️ 全部未看", key=f"allunwatch_{bvid}", width="stretch"):
                apply_batch(bvid, 1, part_total, "未看", "不修改", -1)
        with qc3:
            with st.popover("⚙️ 批量设置（范围 / 理解程度 / 刷数）", width="stretch"):
                st.caption("按分P序号范围批量设置，留“不修改”则该字段不变。")
                rc1, rc2 = st.columns(2)
                with rc1:
                    p_start = st.number_input(
                        "从第P", min_value=1, max_value=part_total,
                        value=1, key=f"start_{bvid}",
                    )
                with rc2:
                    p_end = st.number_input(
                        "到第P", min_value=1, max_value=part_total,
                        value=part_total, key=f"end_{bvid}",
                    )
                b_watch = st.selectbox(
                    "是否看完", ["不修改", "已看", "未看"],
                    key=f"bwatch_{bvid}",
                )
                b_under = st.selectbox(
                    "理解程度", ["不修改", "懂", "半懂", "不懂"],
                    key=f"bunder_{bvid}",
                )
                b_times = st.number_input(
                    "刷了几遍（-1 表示不修改）",
                    min_value=-1, max_value=9999, value=-1, step=1,
                    key=f"btimes_{bvid}",
                )
                if st.button(
                    "应用批量设置", key=f"apply_{bvid}",
                    type="primary", width="stretch",
                ):
                    apply_batch(
                        bvid, p_start, p_end, b_watch, b_under, int(b_times)
                    )

        edited = st.data_editor(
            group,
            width="stretch",
            num_rows="fixed",
            column_order=SUB_COLUMNS,
            key=f"editor_{bvid}",
            column_config={
                "视频标题": st.column_config.TextColumn(
                    "视频标题", disabled=True
                ),
                "BV号": st.column_config.TextColumn(
                    "BV号", disabled=True
                ),
                "分P序号": st.column_config.NumberColumn(
                    "分P序号", disabled=True, width=65, format="%d"
                ),
                "分P标题": st.column_config.TextColumn(
                    "分P标题", disabled=True, width=340
                ),
                "是否看完": st.column_config.CheckboxColumn(
                    "是否看完", default=False, width=85
                ),
                "理解程度": st.column_config.SelectboxColumn(
                    "理解程度", options=UNDERSTAND_OPTS,
                    default="不懂", width=95
                ),
                "刷了几遍": st.column_config.NumberColumn(
                    "刷了几遍", min_value=0, max_value=9999, step=1,
                    default=0, width=85, format="%d"
                ),
                "备注": st.column_config.TextColumn(
                    "备注", default="", width=220,
                    help="可随意填写 Markdown 笔记"
                ),
            },
            hide_index=True,
        )
        edited_groups.append(edited)

# 合并所有分表的编辑结果，恢复原始行顺序
if edited_groups:
    st.session_state.df = normalize_df(pd.concat(edited_groups).sort_index())

# ---------- 回填进度统计看板（表格上方） ----------
latest = st.session_state.df
total = len(latest)
done = int(latest["是否看完"].sum()) if total else 0
rate_text = f"{(done / total * 100):.1f}%" if total else "0.0%"
with metrics_placeholder.container():
    col1, col2, col3 = st.columns(3)
    col1.metric("总课时（总P数）", total)
    col2.metric("已完成", done)
    col3.metric("完成率", rate_text)

# ---------- 保存按钮 ----------
st.write("")
if st.button("💾 保存当前进度", type="primary", use_container_width=False):
    try:
        out = normalize_df(st.session_state.df)
        save_data(out)
        st.session_state.df = out
        st.success(f"进度已保存到 {CSV_PATH} ✅")
    except PermissionError:
        st.error(f"保存失败：{CSV_PATH} 被其他程序占用（如 Excel 打开中），请关闭后重试。")
    except OSError as e:
        st.error(f"保存失败（文件写入错误）：{e}")
    except Exception as e:
        st.error(f"保存失败：{e}")
