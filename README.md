# Memory Map — Streamlit starter

A small shared map-story prototype for friends. It supports:
- a map centered on China and Korea
- clicking the map to select coordinates
- adding a short text story at the selected location
- displaying saved stories as map markers and popups
- persistent storage in Supabase
- a simple shared-password gate

## 1. Create a Supabase project
1. Create a project at https://supabase.com/.
2. Open SQL Editor and run `supabase_schema.sql`.
3. In Project Settings / API, copy the project URL and the **service-role key** (or the secret key equivalent available in your dashboard).
4. Treat the service-role key as highly sensitive. Do not commit it to GitHub or expose it in browser-side code.

## 2. Run locally
1. Install Python 3.10 or later.
2. Create and activate a virtual environment (optional but recommended).
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
5. Fill in `APP_PASSWORD`, `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`.
6. Start the app:

   ```bash
   streamlit run app.py
   ```

## 3. Deploy with GitHub + Streamlit Community Cloud
1. Create a GitHub repository and upload the project files.
2. **Do not upload `.streamlit/secrets.toml`.** It is excluded by `.gitignore`.
3. In https://share.streamlit.io/, create an app from the repository and select `app.py`.
4. Open the deployed app's Settings / Secrets and add:

   ```toml
   APP_PASSWORD = "your-private-shared-password"
   SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
   SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
   ```

5. Deploy, then share the URL and password only with friends you trust.

## Important limitations
- This is a prototype, not a hardened private social network.
- Anyone with the shared password can add records. There is no per-person identity, edit/delete flow, moderation queue, or rate limiting yet.
- The app uses the Supabase service-role key on the server. Never expose it in client-side JavaScript, browser code, or a public repository.
- OpenStreetMap is used for the prototype. Review tile usage policies, map attribution, coordinate alignment, and applicable China map requirements before broader deployment.
- Streamlit's interface reruns Python on interaction. If map interactions become awkward, consider a dedicated Leaflet/MapLibre component in a later iteration.
