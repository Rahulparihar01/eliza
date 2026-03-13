# Testing the RAG Pipeline with Your Own PDFs

This guide walks you through running PDFs (e.g. from a SharePoint folder) through the deployed RAG pipeline: **upload → process (classify, extract, chunk, embed) → index into OpenSearch → query via MCP**.

You can test in two ways:

1. **Manual upload to S3** (fastest) — Upload PDFs to the raw S3 bucket, then trigger the document pipeline. No SharePoint credentials needed.
2. **SharePoint → S3 sync** — Use the SharePoint sync DAG to mirror a document library into S3, then run the document pipeline (requires Azure AD app and credentials in Secrets Manager).

---

## Prerequisites

- Terraform apply already completed (you have the outputs below).
- AWS CLI configured (`aws sts get-caller-identity` works).
- PDFs available locally (downloaded from SharePoint or any source).

---

## Step 1: Apply Startup Script (so MWAA knows your buckets and OpenSearch)

The DAGs expect environment variables `S3_RAW_BUCKET`, `S3_PROCESSED_BUCKET`, and `RAG_OPENSEARCH_HOST`. Terraform can inject these via an MWAA startup script.

From repo root:

```bash
cd terraform/rag-pipeline
terraform apply
```

This uploads `startup.sh` to the DAG bucket and configures MWAA to use it. **Note:** Updating the MWAA environment (e.g. adding a startup script) can take **15–20 minutes**. You can continue with Step 2 while MWAA updates.

If you prefer not to change MWAA yet, you can set these in the **AWS Console → MWAA → your environment → Edit → Environment variables** (if your MWAA version supports custom env vars), or skip and rely on the deploy script’s defaults after you set them once.

---

## Step 2: Deploy DAGs and Plugins to S3

From the **repo root**:

```bash
./terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh \
  --bucket "$(terraform -chdir=terraform/rag-pipeline output -raw s3_dags_bucket)" \
  --region us-east-1
```

This uploads:

- `dags/` (including `document_pipeline.py`, `sharepoint_sync.py`, etc.)
- `requirements/requirements.txt`
- `eliza-rag-ingestion` wheel and `plugins/plugins.zip`

MWAA will load the new DAGs within a few minutes.

---

## Step 3: Upload Your PDFs to the Raw S3 Bucket

The **document_pipeline** DAG scans the prefix `sharepoint/` in the raw bucket when no specific keys are passed. So put your files under that prefix.

Using your Terraform outputs:

- **Raw bucket:** `eliza-rag-raw-documents` (or `terraform -chdir=terraform/rag-pipeline output -raw s3_raw_bucket`)

**Option A — AWS CLI (recommended for a few files):**

```bash
# Create a folder under sharepoint/ (e.g. mirror your SharePoint folder name)
aws s3 cp /path/to/your/file1.pdf s3://eliza-rag-raw-documents/sharepoint/test-run/file1.pdf --region us-east-1
aws s3 cp /path/to/your/file2.pdf s3://eliza-rag-raw-documents/sharepoint/test-run/file2.pdf --region us-east-1
```

**Option B — Sync a whole directory:**

```bash
aws s3 sync /path/to/local/pdf/folder/ s3://eliza-rag-raw-documents/sharepoint/my-folder/ --region us-east-1
```

**Option C — SharePoint sync DAG**

If you have SharePoint credentials in Secrets Manager and have configured the sync DAG, it will write under `sharepoint/` for you. Then you only need to trigger the document pipeline (Step 5).

---

## Step 4: Access the MWAA Airflow UI

MWAA runs in a **private VPC**. The webserver URL is a VPC endpoint hostname, e.g.:

```text
f375cc90-1995-4b96-856e-82ed3d1f4bdb-vpce.c22.airflow.us-east-1.on.aws
```

You can reach it by:

1. **VPN / private network** — If your machine is on a VPN that can reach the RAG pipeline VPC (e.g. same AWS account and VPC peering or private access), open:  
   `https://<mwaa_webserver_url>`
2. **AWS Session Manager port forwarding** — From a bastion or EC2 in the same VPC, use SSM port forwarding to forward 443 to the MWAA endpoint, then open `https://localhost:443` (or the port you use).
3. **Trigger DAG via AWS CLI (no UI)** — You can trigger the DAG without opening the UI (see below).

To get the exact URL:

```bash
terraform -chdir=terraform/rag-pipeline output -raw mwaa_webserver_url
# Then open https://<that-value> in a browser (if you have network access).
```

---

## Step 5: Trigger the Document Pipeline

The **document_pipeline** DAG has `schedule=None`; it runs only when triggered.

**From the Airflow UI:**

1. Open the DAGs list, find **document_pipeline**.
2. Turn the DAG **On** (toggle).
3. Click **Trigger DAG** (play button). No parameters needed — it will scan `s3://eliza-rag-raw-documents/sharepoint/` and process all objects found.

**From the AWS CLI (no UI):**

Use the MWAA CreateCliToken API, then call the Airflow CLI endpoint to trigger the DAG. The token is valid for **60 seconds**.

```bash
# Create a CLI token and get webserver hostname
TOKEN_JSON=$(aws mwaa create-cli-token --name eliza-rag-mwaa --region us-east-1)
CLI_TOKEN=$(echo "$TOKEN_JSON" | jq -r '.CliToken')
HOST=$(echo "$TOKEN_JSON" | jq -r '.WebServerHostname')

# Trigger the DAG via MWAA CLI endpoint
curl -X POST "https://$HOST/aws_mwaa/cli" \
  -H "Authorization: Bearer $CLI_TOKEN" \
  -H "Content-Type: text/plain" \
  -d "dags trigger document_pipeline"
```

If your network cannot reach the MWAA endpoint, run this from an EC2 instance or tool that has access (e.g. in the same VPC or via Session Manager).

---

## Step 6: Monitor the Run

- **In the UI:** Open **document_pipeline** → **Grid** or **Graph** and watch task states (resolve_files → classify → route → process_* → embed_and_index).
- **Logs:** Use **AWS CloudWatch → Log groups** for `airflow-eliza-rag-mwaa-*` (scheduler, worker, etc.) to debug failures.

The pipeline will:

1. List objects under `sharepoint/` in the raw bucket.
2. Classify each file (PDF → PDF category).
3. Run the PDF preprocessor (OCR/text extraction via `eliza_rag`).
4. Chunk text, embed with Bedrock Titan, and index into OpenSearch Serverless.

---

## Step 7: Query Your Data (MCP / API Gateway)

After the DAG run completes, embeddings are in OpenSearch. You can query via the **MCP server** behind API Gateway.

**API Gateway URL (from Terraform):**

```bash
terraform -chdir=terraform/rag-pipeline output -raw api_gateway_url
# e.g. https://k0z3na8vm1.execute-api.us-east-1.amazonaws.com
```

Use your MCP client (e.g. ChatGPT Enterprise with MCP, or a small script) with:

- **Endpoint:** `https://<api_gateway_url>/mcp` (or the path you configured).
- **Auth:** API key in the header (value from Secrets Manager: `eliza-rag/development/mcp-api-key`, or the key you set in `mcp_api_key` in tfvars).

MCP tools typically exposed include vector search, keyword search, and doc fetch — so you can ask questions over the content of your uploaded PDFs.

---

## Summary Checklist

| Step | Action |
|------|--------|
| 1 | `terraform apply` in `terraform/rag-pipeline` (startup script + MWAA config). |
| 2 | Run `deploy_mwaa_assets.sh` with your DAG bucket and region. |
| 3 | Upload PDFs to `s3://eliza-rag-raw-documents/sharepoint/<any-path>/`. |
| 4 | Access MWAA UI (VPN/SSM) or use CLI to trigger the DAG. |
| 5 | Trigger **document_pipeline** (UI or `POST .../dagRuns`). |
| 6 | Monitor in Airflow/CloudWatch until `embed_and_index` succeeds. |
| 7 | Query via API Gateway MCP endpoint with your MCP API key. |

---

## Optional: Use the SharePoint Sync DAG

To pull from your **team SharePoint** instead of uploading manually, follow the setup below. The sync DAG uses Microsoft Graph API to mirror all document libraries (drives) under your site into S3, then triggers the document pipeline when new files are found.

---

### 1. Create an Azure AD app registration (one-time)

1. In **Azure Portal** → **Microsoft Entra ID** (or **Azure Active Directory**) → **App registrations** → **New registration**.
2. Name it (e.g. `Eliza RAG SharePoint Sync`), leave supported account type as single tenant, register.
3. Note:
   - **Application (client) ID** → this is `sharepoint_client_id`.
   - **Directory (tenant) ID** (from the app’s Overview) → this is `sharepoint_tenant_id`.
4. **Certificates & secrets** → **New client secret** → add description, choose expiry → **Add**. Copy the **Value** immediately (this is `sharepoint_client_secret`; it’s shown only once).
5. **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions**:
   - Add **Sites.Read.All** (read SharePoint site and drive content).
   - If you need to write metadata, add **Sites.ReadWrite.All** instead.
6. **Grant admin consent** for your tenant (e.g. **Grant admin consent for &lt;Your org&gt;**).

---

### 2. Get your SharePoint site ID

The pipeline needs the **site ID** of your team SharePoint site (the document library is discovered from the site’s drives).

**Option A — From the site URL (recommended)**

If your team site URL is:

`https://<tenant>.sharepoint.com/sites/<SiteName>`

then the site path is `/sites/<SiteName>`. Use Microsoft Graph to resolve it to a site ID:

- **Graph Explorer:** go to [https://developer.microsoft.com/graph/graph-explorer](https://developer.microsoft.com/graph/graph-explorer), sign in, then run:
  ```http
  GET https://graph.microsoft.com/v1.0/sites/<tenant>.sharepoint.com:/sites/<SiteName>
  ```
  Replace `<tenant>` with your SharePoint hostname (e.g. `contoso`) and `<SiteName>` with the site path (e.g. `MyTeam`). The response **`id`** is your `sharepoint_site_id` (a long string with commas and GUIDs).

- **PowerShell** (with `Microsoft.Graph` module or token):
  ```powershell
  $url = "https://graph.microsoft.com/v1.0/sites/contoso.sharepoint.com:/sites/MyTeam"
  Invoke-RestMethod -Uri $url -Headers @{ Authorization = "Bearer $accessToken" }
  ```
  Use the `id` from the response.

**Option B — From a Teams team**

If the SharePoint site is tied to a Microsoft Team: **Teams** → team → **…** → **Get link to team** or use Graph `GET /groups/{group-id}/sites/root` to get the linked site; the response `id` is the site ID.

---

### 3. Store credentials and wire them to MWAA

The sync DAG reads credentials from **environment variables** in MWAA. Do both steps below.

**3a. Terraform (Secrets Manager)**

Put the four values in `terraform/rag-pipeline/terraform.tfvars` (or another `.tfvars` file; keep it out of version control):

```hcl
sharepoint_tenant_id     = "your-azure-tenant-id"
sharepoint_client_id     = "your-app-client-id"
sharepoint_client_secret = "your-client-secret-value"
sharepoint_site_id       = "your-sharepoint-site-id"
```

Then apply so the secret is stored in AWS Secrets Manager (and can be rotated there later):

```bash
cd terraform/rag-pipeline
terraform apply
```

**3b. MWAA environment variables**

The DAG runs inside MWAA and reads `SHAREPOINT_*` from the environment. Add them in the AWS Console:

1. **AWS Console** → **Amazon MWAA** → select your environment (e.g. `eliza-rag-mwaa`) → **Edit**.
2. Under **Environment variables**, add (you can copy the values from Secrets Manager or from your tfvars):

   | Key                      | Value              |
   |--------------------------|--------------------|
   | `SHAREPOINT_TENANT_ID`   | Your Azure tenant ID |
   | `SHAREPOINT_CLIENT_ID`   | Your app (client) ID |
   | `SHAREPOINT_CLIENT_SECRET` | Your client secret   |
   | `SHAREPOINT_SITE_ID`     | Your SharePoint site ID |

3. Save. MWAA will update (typically 15–20 minutes).

---

### 4. Deploy DAGs and turn on the sync DAG

If you haven’t already:

```bash
# From repo root
./terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh \
  --bucket "$(terraform -chdir=terraform/rag-pipeline output -raw s3_dags_bucket)" \
  --region us-east-1
```

Then in the **Airflow UI** (or via CLI):

1. Find the DAG **sharepoint_s3_sync**.
2. Turn it **On**. It runs on a schedule (default every 15 minutes) and syncs all document libraries under your site to `s3://<raw-bucket>/sharepoint/`.
3. When the sync finds new or changed files, it automatically triggers **document_pipeline**; otherwise trigger **document_pipeline** manually after a sync run (see Step 5 in the main guide).

---

### 5. Verify

- In **Airflow** → **sharepoint_s3_sync** → **Grid** or **Logs**: confirm `list_drives` and `fetch_delta` succeed. If you see “SharePoint credentials not fully configured”, re-check the four MWAA environment variables.
- In **S3**: look under `s3://<raw-bucket>/sharepoint/<drive-id>/...` for synced files.
- After sync, run or wait for **document_pipeline** and then query via MCP (Step 7 in the main guide).

---

## Troubleshooting

### "Unable to read .../plugins/plugins.zip" (ValidationException)

**Cause:** MWAA is configured to load plugins from `plugins/plugins.zip` in the DAG bucket, but that object does not exist in S3. Terraform does **not** upload it; it only tells MWAA where to find it. The file is created and uploaded by the deploy script.

**Fix:** From repo root, upload DAGs and plugins to the existing bucket, then re-run Terraform:

```bash
./terraform/rag-pipeline/scripts/deploy_mwaa_assets.sh \
  --bucket "$(terraform -chdir=terraform/rag-pipeline output -raw s3_dags_bucket)" \
  --region us-east-1
```

Then:

```bash
terraform -chdir=terraform/rag-pipeline apply
```

**If the deploy script fails** (e.g. "Package directory not found"): ensure you have `packages/eliza-rag-ingestion` and `dags/` at repo root (same layout as this repo). The script builds the wheel and zips it into `plugins.zip` before uploading.

**To run without custom plugins** (temporary): set `mwaa_plugins_s3_path = ""` in `terraform.tfvars` (or pass `-var="mwaa_plugins_s3_path="`). MWAA will then not require a plugins file. DAGs that depend on the `eliza-rag-ingestion` package may fail until plugins are deployed.

### Airflow UI / SSO hanging or 403 when opening the Airflow UI

**Cause:** Opening the Airflow UI (e.g. from [MWAA → Open Airflow UI](https://us-east-1.console.aws.amazon.com/mwaa/home?region=us-east-1#environments) or SSO) uses **your** IAM identity to call `airflow:CreateWebLoginToken`. If that identity does not have permission, the request hangs or returns 403.

**Fix:** Attach one of the following to the **IAM user or role you use to sign into the AWS Console** (see "Which role/user?" below)—**not** to the MWAA service-linked role.

- **Option A (this stack):** Attach the policy created by Terraform:
  ```bash
  terraform -chdir=terraform/rag-pipeline output -raw mwaa_ui_access_policy_arn
  ```
  Then in IAM → Users (or Roles) → **your** identity → Add permissions → Attach policies → select `eliza-rag-mwaa-ui-access`.

- **Option B (AWS managed):** Attach the AWS managed policy **AmazonMWAAWebServerAccess** to the same user or role.

**Which role/user?**  
- **AWSServiceRoleForAmazonMWAA** is a **service-linked role** used by the MWAA service itself. Do **not** attach the UI policy here; it won't fix the blank screen.  
- **AWSReservedSSO_...** roles appear only if you sign in via **IAM Identity Center (SSO)**; AWS creates them when you set up permission sets. You don't create them manually. If you don't see one, you may be signing in as an **IAM user** instead.  
- **To find your identity:** IAM → **Users** (look for a user matching your sign-in, e.g. ryanc@eliza.com) or IAM → **Roles** (if you use SSO, search for your permission set name or "SSO"). Attach the policy to that user or role.

After attaching, sign out and back into the console (or refresh if using SSO), then try "Open Airflow UI" again.

**If the UI still shows a blank screen**, work through these in order:

1. **Confirm the right identity has the permission**  
   The permission must be on the **exact** IAM user or role you use when you see your name in the top-right (e.g. ryanc@eliza.com). If you sign in via **IAM Identity Center (SSO)**, that is usually an **IAM role** (e.g. `AWSReservedSSO_...`), not an IAM user. Attach `eliza-rag-mwaa-ui-access` (or **AmazonMWAAWebServerAccess**) to that **role** in IAM → Roles, not to a user. Then sign out and back in and try again.

2. **Test the token API with the same credentials**  
   From a terminal where your AWS CLI uses the same identity as the console (same profile or SSO login), run:
   ```bash
   aws mwaa create-web-login-token --name eliza-rag-mwaa --region us-east-1
   ```
   - If you get **AccessDenied** or **Unauthorized**: the identity used by the CLI does not have `airflow:CreateWebLoginToken`. Attach the UI access policy to that identity (the role or user the CLI is using).
   - If you get a JSON response with `WebServerHostname` and `WebToken`: IAM is fine; the problem is likely browser or redirect (try step 3 or 4).

3. **Try an incognito/private window**  
   Corrupted or stale cookies for `*.aws.amazon.com` or the Airflow URL can cause redirects to hang or show a blank page. Open a private/incognito window, sign in to the AWS Console again, then go to MWAA → Open Airflow UI.

4. **Check CloudWatch webserver logs**  
   In CloudWatch → Log groups → **airflow-eliza-rag-mwaa-webserver** (or `airflow-<project>-mwaa-webserver`), open the latest log stream and look for errors around the time you tried to open the UI (e.g. auth or token errors). That will confirm whether the request is reaching the Airflow webserver and what fails.

**Note:** This MWAA environment runs in **private subnets**. The "Open Airflow UI" link from the console uses an AWS-managed URL; your browser does not need to be inside the VPC. So a blank screen is usually IAM (wrong identity or policy not attached) or browser/cookies, not VPC/network.

### "Site can't be reached" after clicking Open Airflow UI

**Cause:** The Airflow webserver is in **private access mode** (`PRIVATE_ONLY`). The login URL is only reachable from inside the VPC, so from your laptop you get "site can't be reached" or connection timeout.

**Fix (recommended for dev):** Use **public** webserver access so the UI is reachable from the internet (still protected by IAM and the one-time token). In `terraform.tfvars` set:

```hcl
mwaa_webserver_access_mode = "PUBLIC_ONLY"
```

Then run `terraform -chdir=terraform/rag-pipeline apply`. MWAA will update (can take 15–20 minutes). After it finishes, sign in again and try "Open Airflow UI"—the URL should load.

**Alternative (keep private):** If you must keep `PRIVATE_ONLY`, you need network access to the VPC: [AWS Client VPN](https://docs.aws.amazon.com/mwaa/latest/userguide/tutorials-private-network-vpn-client.html), a bastion host with SSH tunnel, or [corporate VPN / Direct Connect](https://repost.aws/knowledge-center/mwaa-connection-timed-out-error). Access is still IAM-protected via the web login token.

---

### Summary: SharePoint-only checklist

| Step | Action |
|------|--------|
| 1 | Create Azure AD app; add client secret; grant **Sites.Read.All** (or **Sites.ReadWrite.All**); admin consent. |
| 2 | Get **SharePoint site ID** (e.g. Graph `GET /sites/<hostname>:/sites/<SiteName>`). |
| 3a | Set `sharepoint_*` in `terraform.tfvars` and run `terraform apply`. |
| 3b | Add the four `SHAREPOINT_*` environment variables in MWAA (Edit environment). |
| 4 | Deploy DAGs; turn **sharepoint_s3_sync** On. |
| 5 | Monitor sync and document pipeline; query via MCP. |

SharePoint sync is optional for testing; manual upload to `sharepoint/` (Step 3 in the main guide) is enough to validate the rest of the pipeline without any SharePoint credentials.
