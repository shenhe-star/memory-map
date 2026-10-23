import html
import streamlit as st
import folium
from streamlit_folium import st_folium
from supabase import create_client
from datetime import datetime

st.set_page_config(
    page_title="Memory Map",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Configuration ----------
def get_setting(name: str) -> str:
    try:
        return str(st.secrets[name])
    except Exception:
        return ""

APP_PASSWORD = get_setting("APP_PASSWORD")
SUPABASE_URL = get_setting("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = get_setting("SUPABASE_SERVICE_ROLE_KEY")

# ---------- Simple shared-password gate ----------
if not APP_PASSWORD:
    st.error(
        "还没有配置访问密码。请在 Streamlit Cloud 的 App settings → Secrets "
        "中添加 APP_PASSWORD；本地运行则填写 .streamlit/secrets.toml。"
    )
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Memory Map")
    st.caption("在地图上的某个地方，留下一段文字。")
    with st.form("login_form"):
        password = st.text_input("访问密码", type="password")
        submitted = st.form_submit_button("进入地图", use_container_width=True)
    if submitted:
        if password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("密码不正确，请再试一次。")
    st.stop()

# ---------- Database ----------
if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    st.error(
        "数据库尚未配置。请在 Streamlit Cloud 的 Secrets 中添加 "
        "SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY。"
    )
    st.stop()

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

supabase = get_supabase()

def fetch_stories():
    result = (
        supabase.table("stories")
        .select("id, latitude, longitude, content, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []

def save_story(latitude: float, longitude: float, content: str):
    return (
        supabase.table("stories")
        .insert({
            "latitude": float(latitude),
            "longitude": float(longitude),
            "content": content.strip(),
        })
        .execute()
    )

# ---------- Page ----------
st.title("Memory Map")
st.caption("中国 · 韩国 | 点击地图上的一个地方，留下一段文字。")

try:
    stories = fetch_stories()
except Exception as exc:
    st.error(
        "读取数据库失败。请检查 Supabase URL、Service Role Key，以及是否已经运行 "
        "supabase_schema.sql。"
    )
    with st.expander("技术错误详情"):
        st.code(str(exc))
    st.stop()

left, right = st.columns([2.25, 1], gap="large")

with left:
    # OpenStreetMap tiles are suitable for a prototype. Review tile-provider
    # terms, China map requirements, and coordinate alignment before public use.
    map_obj = folium.Map(
        location=[35.5, 124.0],
        zoom_start=4,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    for story in stories:
        content = html.escape(str(story.get("content", ""))).replace("\n", "<br>")
        created = story.get("created_at", "")
        popup_html = f"""
        <div style="width: 220px; max-width: 220px; white-space: normal;
                    font-family: sans-serif; line-height: 1.5;">
          <div style="font-size: 13px; color: #777; margin-bottom: 6px;">
            {html.escape(str(created)[:16])}
          </div>
          <div style="font-size: 14px;">{content}</div>
        </div>
        """
        folium.Marker(
            location=[story["latitude"], story["longitude"]],
            tooltip="点击阅读这条记录",
            popup=folium.Popup(popup_html, max_width=280),
            icon=folium.Icon(color="darkpurple", icon="comment", prefix="fa"),
        ).add_to(map_obj)

    map_result = st_folium(
        map_obj,
        height=640,
        use_container_width=True,
        returned_objects=["last_clicked"],
        key=f"memory_map_{st.session_state.get('map_version', 0)}",
    )

    clicked = map_result.get("last_clicked") if map_result else None
    if clicked and "lat" in clicked and "lng" in clicked:
        new_location = (round(float(clicked["lat"]), 6), round(float(clicked["lng"]), 6))
        if st.session_state.get("selected_location") != new_location:
            st.session_state.selected_location = new_location

with right:
    st.subheader("留下记录")
    st.write("在左侧地图点击你想记录的地点，再写下文字。")

    selected = st.session_state.get("selected_location")
    if selected:
        st.success(f"已选位置：{selected[0]:.5f}, {selected[1]:.5f}")
    else:
        st.info("还没有选择地点。请先点击地图。")

    with st.form("story_form", clear_on_submit=True):
        content = st.text_area(
            "你的文字",
            placeholder="在这里写下一段记忆……",
            height=220,
            max_chars=3000,
        )
        submit_story = st.form_submit_button(
            "保存记录",
            use_container_width=True,
            disabled=selected is None,
        )

    if submit_story:
        if not content.strip():
            st.warning("请先输入文字。")
        elif selected is None:
            st.warning("请先在地图上选择一个地点。")
        else:
            try:
                save_story(selected[0], selected[1], content)
                st.session_state.selected_location = None
                st.session_state.map_version = st.session_state.get("map_version", 0) + 1
                st.success("记录已保存。刷新地图后也会保留。")
                st.rerun()
            except Exception as exc:
                st.error("保存失败，请检查数据库设置。")
                with st.expander("技术错误详情"):
                    st.code(str(exc))

    st.divider()
    st.subheader(f"已保存的记录（{len(stories)}）")
    if not stories:
        st.caption("地图上还没有记录。你可以先创建第一条。")
    else:
        for idx, story in enumerate(stories):
            snippet = str(story["content"]).strip().replace("\n", " ")
            if len(snippet) > 110:
                snippet = snippet[:110] + "…"
            with st.expander(f"记录 {len(stories) - idx} · {story['latitude']:.3f}, {story['longitude']:.3f}"):
                st.write(story["content"])
                st.caption(f"创建时间：{story.get('created_at', '未知')}")

st.caption(
    "原型说明：目前所有持有访问密码的人都能添加记录；本版本暂未提供单条记录编辑、删除、"
    "投稿审核或个人身份管理。请只分享给信任的朋友。"
)
