# Infrastructure as Code (Bicep)

Declares every Azure resource this project uses: Azure AI Search, Azure OpenAI (+ two model
deployments), Log Analytics + Application Insights (+ alerts + monitoring workbook), and the
Container Apps environment (+ Container Registry + the `api`/`ui` container apps).

## Structure

```
infra/
  main.bicep                  — orchestrator, wires the modules together
  main.bicepparam              — non-secret parameters (safe to commit)
  modules/search.bicep         — Azure AI Search
  modules/openai.bicep         — Azure OpenAI account + gpt-5-mini + text-embedding-3-small
  modules/monitoring.bicep     — Log Analytics, App Insights, action group, alerts, workbook
  modules/containerapps.bicep  — Container Registry, Container Apps environment, api + ui apps
```

## Secrets

No API key is ever written into any `.bicep`/`.bicepparam` file. `modules/containerapps.bicep`
pulls the Azure OpenAI key, Azure AI Search admin key, and ACR password directly from those
resources at deploy time via Bicep's `listKeys()` / `listAdminKeys()` / `listCredentials()`
functions, and wires them straight into the Container Apps' native `secrets` block. Nothing to
type or paste.

## Deploying

One-time (if not already registered on this subscription):

```
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.ContainerRegistry
```

**Always preview before applying** — this reconciles against resources that already exist and
hold real data (Application Insights has telemetry history, Azure AI Search has indexed
documents):

```
az deployment group what-if -g rg-clinical-rag -f infra/main.bicep -p infra/main.bicepparam
```

Existing resources (Search, OpenAI, action group, both alerts) should show as **no change**.
Only the new resources (Log Analytics workspace, Container Registry, Container Apps environment,
the two container apps) should show as **create**. Application Insights may show an update to
`WorkspaceResourceId` (relinking from its current auto-managed workspace to the explicit one this
template creates) — this is a supported, non-destructive property update, but confirm the diff
doesn't show anything beyond that before proceeding.

Once the what-if output looks right:

```
az deployment group create -g rg-clinical-rag -f infra/main.bicep -p infra/main.bicepparam
```

## After first deploy: pushing images

The container apps are created pointing at `:latest` images in the new registry, but nothing has
been pushed there yet — the apps won't serve traffic until an image exists. One-time manual push
to prove the infra works (ongoing pushes become GitHub Actions' job):

```
az acr login --name <acrLoginServer from the deployment output, without ".azurecr.io">
docker tag clinical-rag-api <acrLoginServer>/clinical-rag-api:latest
docker tag clinical-rag-ui <acrLoginServer>/clinical-rag-ui:latest
docker push <acrLoginServer>/clinical-rag-api:latest
docker push <acrLoginServer>/clinical-rag-ui:latest
az containerapp revision restart -g rg-clinical-rag -n ca-clinical-rag-api --revision <latest revision name>
az containerapp revision restart -g rg-clinical-rag -n ca-clinical-rag-ui --revision <latest revision name>
```
