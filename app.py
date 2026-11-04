import html
import uuid
import streamlit as st
import streamlit.components.v1 as components
import folium
from streamlit_folium import st_folium
from supabase import create_client

st.set_page_config(
    page_title="Memory Map",
    page_icon="🌸",
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
ADMIN_PASSWORD = get_setting("ADMIN_PASSWORD")
STORAGE_BUCKET = "memory-images"

# ---------- Soft pink theme ----------
st.markdown("""
<style>
:root {
    --pink-bg: #fff1f4;
    --pink-card: #fffafb;
    --pink-accent: #d889a2;
    --pink-dark: #754454;
}
.stApp { background: var(--pink-bg); }
[data-testid="stHeader"] { background: rgba(255,241,244,.88); }
[data-testid="stSidebar"] { background: #fbe6ec; }
.block-container { padding-top: 2rem; }
h1, h2, h3 { color: var(--pink-dark); }
.stButton > button, .stFormSubmitButton > button {
    border-radius: 18px;
    border: 1px solid #e7b8c7;
}
div[data-testid="stExpander"] {
    background: var(--pink-card);
    border: 1px solid #f0d4dd;
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

# ---------- Shared password gate ----------
if not APP_PASSWORD:
    st.error("尚未配置 APP_PASSWORD。请在 Streamlit Cloud → App settings → Secrets 中添加。")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🌸 Memory Map")
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
    st.error("数据库尚未配置，请检查 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY。")
    st.stop()

@st.cache_resource
def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

supabase = get_supabase()

def fetch_stories():
    result = (
        supabase.table("stories")
        .select("id, latitude, longitude, content, created_at, image_url, image_path")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []

def upload_image(uploaded_file):
    suffix = uploaded_file.name.rsplit(".", 1)[-1].lower() if "." in uploaded_file.name else ""
    allowed = {"jpg", "jpeg", "png", "webp"}
    if suffix not in allowed:
        raise ValueError("图片仅支持 JPG、JPEG、PNG、WEBP 格式。")
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValueError("单张图片不能超过 5MB。")
    path = f"{uuid.uuid4().hex}.{suffix}"
    content_type = uploaded_file.type or "application/octet-stream"
    supabase.storage.from_(STORAGE_BUCKET).upload(
        path,
        uploaded_file.getvalue(),
        file_options={"content-type": content_type, "upsert": "false"},
    )
    public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(path)
    return path, public_url

def save_story(latitude, longitude, content, image_path=None, image_url=None):
    return supabase.table("stories").insert({
        "latitude": float(latitude),
        "longitude": float(longitude),
        "content": content.strip(),
        "image_path": image_path,
        "image_url": image_url,
    }).execute()

def delete_story(story):
    # Delete stored image first, then delete its database row.
    image_path = story.get("image_path")
    if image_path:
        supabase.storage.from_(STORAGE_BUCKET).remove([image_path])
    supabase.table("stories").delete().eq("id", story["id"]).execute()

# ---------- Music player ----------
st.title("🌸 Memory Map")
st.caption("中国 · 韩国 | 点击地图上的一个地方，留下一段文字。")

st.markdown("### 🎵 陈粒 · ⭐️")
st.caption("点击播放按钮收听。音乐由网易云音乐提供，能否播放取决于歌曲版权、地区和平台登录状态。")
components.html("""
<div style="max-width:520px; margin:0 auto; padding:10px 14px;
            background:#fffafb; border:1px solid #f0d4dd;
            border-radius:16px; box-shadow:0 3px 14px rgba(160,90,115,.08);">
  <iframe title="网易云音乐播放器"
    src="https://music.163.com/outchain/player?type=2&id=2734045175&auto=0&height=66"
    width="100%" height="86" frameborder="0" marginwidth="0" marginheight="0"
    allow="autoplay; encrypted-media" loading="lazy">
  </iframe>
  <div style="text-align:center; font:12px sans-serif; color:#9a7180;">
    <a href="https://music.163.com/song?id=2734045175" target="_blank"
       rel="noopener noreferrer" style="color:#a96e83;text-decoration:none;">
       在网易云音乐打开原歌曲
    </a>
  </div>
</div>
""", height=118)

try:
    stories = fetch_stories()
except Exception as exc:
    st.error("读取数据库失败。请确认已运行升级版 SQL，并检查 Supabase 配置。")
    with st.expander("技术错误详情"):
        st.code(str(exc))
    st.stop()

left, right = st.columns([2.25, 1], gap="large")

with left:
    map_obj = folium.Map(
        location=[35.5, 124.0],
        zoom_start=4,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    for story in stories:
        safe_content = html.escape(str(story.get("content", ""))).replace("\n", "<br>")
        image_html = ""
        if story.get("image_url"):
            safe_url = html.escape(str(story["image_url"]), quote=True)
            image_html = (
                f'<img src="{safe_url}" '
                'style="width:100%;max-height:180px;object-fit:contain;'
                'border-radius:8px;margin-top:8px;" />'
            )
        popup_html = f"""
        <div style="width:230px;max-width:230px;white-space:normal;
                    font-family:sans-serif;line-height:1.5;">
          <div style="font-size:12px;color:#987786;margin-bottom:6px;">
            {html.escape(str(story.get("created_at", ""))[:16])}
          </div>
          <div style="font-size:14px;color:#543746;">{safe_content}</div>
          {image_html}
        </div>
        """
        folium.Marker(
            location=[story["latitude"], story["longitude"]],
            tooltip="点击阅读这条记录",
            popup=folium.Popup(popup_html, max_width=280),
            icon=folium.Icon(color="pink", icon="heart", prefix="fa"),
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
    st.subheader("💌 留下记录")
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
            height=200,
            max_chars=3000,
        )
        image_file = st.file_uploader(
            "为这段记忆添加图片（可选）",
            type=["jpg", "jpeg", "png", "webp"],
            help="支持 JPG、PNG、WEBP，单张最大 5MB。",
        )
        submit_story = st.form_submit_button(
            "保存这段记忆",
            use_container_width=True,
            disabled=selected is None,
        )

    if submit_story:
        if not content.strip():
            st.warning("请先输入文字。")
        elif selected is None:
            st.warning("请先在地图上选择一个地点。")
        else:
            uploaded_path = None
            try:
                image_url = None
                if image_file is not None:
                    uploaded_path, image_url = upload_image(image_file)
                save_story(selected[0], selected[1], content, uploaded_path, image_url)
                st.session_state.selected_location = None
                st.session_state.map_version = st.session_state.get("map_version", 0) + 1
                st.success("记忆已保存。")
                st.rerun()
            except Exception as exc:
                if uploaded_path:
                    try:
                        supabase.storage.from_(STORAGE_BUCKET).remove([uploaded_path])
                    except Exception:
                        pass
                st.error("保存失败。请检查图片存储桶和数据库升级是否完成。")
                with st.expander("技术错误详情"):
                    st.code(str(exc))

    st.divider()
    st.subheader(f"已保存的记忆（{len(stories)}）")

    if not stories:
        st.caption("地图上还没有记录。你可以先创建第一条。")
    else:
        for idx, story in enumerate(stories):
            title = f"记忆 {len(stories) - idx} · {story['latitude']:.3f}, {story['longitude']:.3f}"
            with st.expander(title):
                st.write(story["content"])
                st.caption(f"创建时间：{story.get('created_at', '未知')}")
                if story.get("image_url"):
                    st.image(story["image_url"], use_container_width=True)

                # Deletion is restricted to the site owner, not every shared-password visitor.
                if ADMIN_PASSWORD:
                    confirm_key = f"confirm_delete_{story['id']}"
                    if st.checkbox("我确认要永久删除这条记忆", key=confirm_key):
                        if st.button("删除这条记忆", key=f"delete_{story['id']}", type="secondary"):
                            try:
                                delete_story(story)
                                st.session_state.map_version = st.session_state.get("map_version", 0) + 1
                                st.success("这条记忆已删除。")
                                st.rerun()
                            except Exception as exc:
                                st.error("删除失败，请检查存储权限和数据库连接。")
                                with st.expander("技术错误详情"):
                                    st.code(str(exc))
                else:
                    st.caption("删除功能尚未启用：请在 Streamlit Secrets 中设置 ADMIN_PASSWORD。")

st.caption(
    "请只与信任的朋友分享访问密码。当前版本没有个人账号；删除权限由单独的管理员密码控制。"
)
