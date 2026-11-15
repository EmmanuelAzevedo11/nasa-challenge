<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

## What Lovable manages

Rules outside this block are the project's own. Change the pieces below in
Lovable, not by hand. With the [Lovable MCP](https://mcp.lovable.dev)
connected, `send_message` asks Lovable to do it; otherwise ask the user to
use the editor.

- **Database.** Do not add or edit `supabase/migrations/` or `drizzle/`.
  Ask Lovable to change the schema.
- **Generated files.** Do not edit a file whose header says it is automatically
  generated.
- **AI gateway.** Keep model calls on Lovable's gateway, and keep
  `LOVABLE_API_KEY` out of browser code.
- **Connectors.** Lovable provides native connectors. `list_connectors` shows
  which are enabled; `add_connector` only returns the dashboard link. When a
  connector is enabled, calls go through the connector gateway and need
  `LOVABLE_API_KEY`. When Lovable does not provide one, users can bring their
  own key and store it in Secrets.
- **Secrets.** Lovable manages them. Do not put secret values in the repo.
<!-- LOVABLE:END -->

## Application architecture
- Render the initial location map in the root shell, require a valid selection before revealing route content, and share its expanded state through the platform provider; keep `/plantio` for planting and redirect legacy `/mapa` links to `/` so map access needs no navigation tab.
- Keep this delivery frontend-only, with typed REST services targeting the team's external FastAPI through `VITE_API_BASE_URL`; no local API handlers, auth or database are required.
- Centralize environmental and agricultural HTTP calls in `src/services/api.ts`; show unavailable states for failed requests.
- Share the selected location and ephemeral chat through the root platform provider so navigation retains context without storing conversations.
- Validate geographic selections with point-in-polygon against the bundled São Paulo boundary; the boundary is sourced from Code for America's click_that_hood Brazil state dataset.
- Keep user-driven query reads in React Query hooks; use independent queries for optional data sources so a failed indicator cannot hide the remaining data.
