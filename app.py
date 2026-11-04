import base64
import html
import uuid
from pathlib import Path

import folium
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium
from supabase import create_client

st.set_page_config(
    page_title="our memory map",
    page_icon="🗺️",
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
ASSET_DIR = Path(__file__).parent / "assets"
BACKGROUND_PATH = ASSET_DIR / "background_portrait.jpg"
HEADER_PHOTO_PATH = ASSET_DIR / "header_photo.jpg"


def image_as_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


background_uri = image_as_data_uri(BACKGROUND_PATH)
background_image = f"url('{background_uri}')" if background_uri else "linear-gradient(135deg,#dceaf4,#f5f7fa)"

# ---------- New visual identity ----------
st.markdown(f"""
<style>
:root {{ --ink:#17385d; --ink-soft:#355574; --navy:#173f70; }}
.stApp {{ background:transparent !important; color:var(--ink); }}
.stApp::before {{
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background-image:linear-gradient(rgba(255,255,255,.48),rgba(255,255,255,.48)), {background_image};
  background-size:cover; background-position:center center; background-repeat:no-repeat;
}}
[data-testid="stAppViewContainer"] > .main {{ position:relative; z-index:1; }}
[data-testid="stHeader"] {{ background:rgba(255,255,255,.16); }}
.block-container {{ max-width:1500px; padding-top:2.1rem; padding-bottom:2rem; }}
.our-title {{
  color:#17385d; font-size:clamp(2.5rem,4vw,3.55rem); font-weight:800;
  line-height:1.08; letter-spacing:-.035em; margin:.1rem 0 1.0rem 0;
  text-shadow:0 1px 12px rgba(255,255,255,.65);
}}
.our-copy {{ color:#18395e; font-size:clamp(.98rem,1.12vw,1.14rem);
  line-height:1.95; font-weight:550; text-shadow:0 1px 9px rgba(255,255,255,.85); }}
.our-copy p {{ margin:0 0 .42rem 0; }}
[data-testid="stImage"] img {{ border-radius:16px; object-fit:cover;
  box-shadow:0 12px 32px rgba(16,45,75,.16); border:1px solid rgba(255,255,255,.8); }}
[data-testid="stVerticalBlockBorderWrapper"] {{
  background:rgba(255,255,255,.70); border:1px solid rgba(255,255,255,.86);
  border-radius:20px; padding:12px 14px; box-shadow:0 10px 34px rgba(24,55,85,.10);
  backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
}}
h1,h2,h3,p,label,.stMarkdown {{ color:var(--ink); }}
.stButton > button,.stFormSubmitButton > button {{
  border-radius:12px; border:1px solid rgba(255,255,255,.7);
  background:#173f70; color:white; font-weight:650;
}}
.stButton > button:hover,.stFormSubmitButton > button:hover {{ background:#245887; color:white; border-color:#d9e7f2; }}
[data-testid="stTextArea"] textarea,[data-testid="stTextInput"] input {{ background:rgba(255,255,255,.9); border-radius:12px; }}
div[data-testid="stExpander"] {{ background:rgba(255,255,255,.74); border:1px solid rgba(255,255,255,.85); border-radius:13px; }}
@media(max-width:800px) {{ .block-container{{padding-left:1rem;padding-right:1rem;}} .our-title{{font-size:2.35rem;}} .our-copy{{font-size:.98rem;line-height:1.8;}} }}
</style>
""", unsafe_allow_html=True)

# ---------- Shared-password gate ----------
if not APP_PASSWORD:
    st.error("尚未配置 APP_PASSWORD。请在 Streamlit Cloud → App settings → Secrets 中添加。")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown('<div class="our-title">our memory map</div>', unsafe_allow_html=True)
    st.caption("我们一起去过很多地方 经历过很多美好。")
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
    if suffix not in {"jpg", "jpeg", "png", "webp"}:
        raise ValueError("图片仅支持 JPG、JPEG、PNG、WEBP 格式。")
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValueError("单张图片不能超过 5MB。")
    path = f"{uuid.uuid4().hex}.{suffix}"
    content_type = uploaded_file.type or "application/octet-stream"
    supabase.storage.from_(STORAGE_BUCKET).upload(
        path, uploaded_file.getvalue(),
        file_options={"content-type": content_type, "upsert": "false"},
    )
    public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(path)
    return path, public_url


def save_story(latitude, longitude, content, image_path=None, image_url=None):
    return supabase.table("stories").insert({
        "latitude": float(latitude), "longitude": float(longitude),
        "content": content.strip(), "image_path": image_path, "image_url": image_url,
    }).execute()


def delete_story(story):
    image_path = story.get("image_path")
    if image_path:
        supabase.storage.from_(STORAGE_BUCKET).remove([image_path])
    supabase.table("stories").delete().eq("id", story["id"]).execute()

# ---------- Header: title + music player on one line, image at upper-right ----------
header_left, header_right = st.columns([2.15, 1], gap="large", vertical_alignment="center")
with header_left:
    title_col, music_col = st.columns([1.18, 1], gap="medium", vertical_alignment="center")
    with title_col:
        st.markdown('<div class="our-title">our memory map</div>', unsafe_allow_html=True)
    with music_col:
        st.markdown('<div style="color:#17385d;font-weight:700;font-size:.95rem;margin:0 0 .25rem .15rem;">♪ 陈粒 · ⭐️</div>', unsafe_allow_html=True)
        components.html("""
        <div style="padding:7px 9px;background:rgba(255,255,255,.82);
                    border:1px solid rgba(255,255,255,.92);border-radius:15px;
                    box-shadow:0 8px 24px rgba(20,50,80,.12);">
          <iframe title="网易云音乐播放器"
            src="https://music.163.com/outchain/player?type=2&id=2734045175&auto=0&height=66"
            width="100%" height="86" frameborder="0" marginwidth="0" marginheight="0"
            allow="autoplay; encrypted-media" loading="lazy"></iframe>
          <div style="text-align:center;font:11px sans-serif;color:#526f8c;">
            <a href="https://music.163.com/song?id=2734045175" target="_blank" rel="noopener noreferrer"
               style="color:#315b83;text-decoration:none;">在网易云音乐打开原歌曲</a>
          </div>
        </div>
        """, height=112)
    st.markdown("""
    <div class="our-copy">
      <p>我们一起去过很多地方 经历过很多美好。</p>
      <p>我想和你看下暴雨的沙漠 看大海亲吻鲨鱼 一起去台北的那个地方 一起体会100种生活 一起在假寐与现实之间两难。</p>
      <p>世界这张地图 还有太多我想和你一起探索。</p>
      <p>你是我三十九度的风 是你给我梦境陪我游戏 让我在现实自由呼吸。谢谢你。</p>
    </div>
    """, unsafe_allow_html=True)
with header_right:
    if HEADER_PHOTO_PATH.exists():
        st.image(str(HEADER_PHOTO_PATH), use_container_width=True)
    else:
        st.warning("找不到 assets/header_photo.jpg，请确认图片文件已上传。")

try:
    stories = fetch_stories()
except Exception as exc:
    st.error("读取数据库失败。请确认已运行图片功能升级 SQL，并检查 Supabase 配置。")
    with st.expander("技术错误详情"):
        st.code(str(exc))
    st.stop()

# ---------- Main content: map left, memory form right ----------
left, right = st.columns([2.05, 1], gap="large")

with left:
    with st.container(border=True):
        map_obj = folium.Map(
            location=[35.5, 124.0], zoom_start=4,
            tiles="OpenStreetMap", control_scale=True,
        )
        for story in stories:
            safe_content = html.escape(str(story.get("content", ""))).replace("\n", "<br>")
            image_html = ""
            if story.get("image_url"):
                safe_url = html.escape(str(story["image_url"]), quote=True)
                image_html = (
                    f'<img src="{safe_url}" style="width:100%;max-height:180px;'
                    'object-fit:contain;border-radius:8px;margin-top:8px;" />'
                )
            popup_html = f"""
            <div style="width:230px;max-width:230px;white-space:normal;font-family:sans-serif;line-height:1.5;">
              <div style="font-size:12px;color:#526f8c;margin-bottom:6px;">{html.escape(str(story.get('created_at',''))[:16])}</div>
              <div style="font-size:14px;color:#17385d;">{safe_content}</div>{image_html}
            </div>"""
            folium.Marker(
                location=[story["latitude"], story["longitude"]],
                tooltip="点击阅读这条记录",
                popup=folium.Popup(popup_html, max_width=280),
                icon=folium.Icon(color="pink", icon="heart", prefix="fa"),
            ).add_to(map_obj)

        map_result = st_folium(
            map_obj, height=640, use_container_width=True,
            returned_objects=["last_clicked"],
            key=f"memory_map_{st.session_state.get('map_version', 0)}",
        )

    clicked = map_result.get("last_clicked") if map_result else None
    if clicked and "lat" in clicked and "lng" in clicked:
        new_location = (round(float(clicked["lat"]), 6), round(float(clicked["lng"]), 6))
        if st.session_state.get("selected_location") != new_location:
            st.session_state.selected_location = new_location

with right:
    with st.container(border=True):
        st.subheader("💌 留下记录")
        st.write("在左侧地图点击你想记录的地点，再写下文字。")
        selected = st.session_state.get("selected_location")
        if selected:
            st.success(f"已选位置：{selected[0]:.5f}, {selected[1]:.5f}")
        else:
            st.info("还没有选择地点。请先点击地图。")

        with st.form("story_form", clear_on_submit=True):
            content = st.text_area("你的文字", placeholder="在这里写下一段记忆……", height=150, max_chars=3000)
            image_file = st.file_uploader(
                "添加图片（可选）", type=["jpg", "jpeg", "png", "webp"],
                help="支持 JPG、PNG、WEBP，单张最大 5MB。",
            )
            submit_story = st.form_submit_button("保存记录", use_container_width=True, disabled=selected is None)

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
                title = f"记忆 {len(stories)-idx} · {story['latitude']:.3f}, {story['longitude']:.3f}"
                with st.expander(title):
                    st.write(story["content"])
                    st.caption(f"创建时间：{story.get('created_at', '未知')}")
                    if story.get("image_url"):
                        st.image(story["image_url"], use_container_width=True)

                    if ADMIN_PASSWORD:
                        if "admin_authenticated" not in st.session_state:
                            st.session_state.admin_authenticated = False
                        with st.expander("管理员：管理或删除记忆"):
                            if not st.session_state.admin_authenticated:
                                admin_try = st.text_input("管理员密码", type="password", key="admin_password_input")
                                if st.button("解锁删除权限", key="unlock_admin"):
                                    if admin_try == ADMIN_PASSWORD:
                                        st.session_state.admin_authenticated = True
                                        st.rerun()
                                    else:
                                        st.error("管理员密码不正确。")
                            else:
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

st.caption("请只与信任的朋友分享访问密码。图片存储桶为公开读取，请勿上传敏感照片。")
