
# ⚡ Setting up Jira Webhooks using Ngrok

Since your backend is running locally on port 8094 (or 8000), Jira (which is in the cloud) cannot access it directly. We use **ngrok** to create a secure tunnel from the internet to your local machine.

## Step 1: Install Ngrok
1. Download ngrok from [ngrok.com](https://ngrok.com/download).
2. Unzip it and place `ngrok.exe` in a folder (or add it to your PATH).

## Step 2: Start Ngrok
Open a **new** terminal window and run:
`ngrok http 8000`

(If your backend is running on a different port, change `8000` to that port. Default for Uvicorn is usually 8000, but check your terminal logs).

## Step 3: Get your Public URL
Ngrok will show a Forwarding URL like:
`https://a1b2-c3d4.ngrok-free.app` -> `http://localhost:8000`

Copy the `https` URL.

## Step 4: Configure Jira Webhook
1. Go to your Jira **System Settings** > **Webhooks**.
   *(URL: https://<your-domain>.atlassian.net/plugins/servlet/webhooks)*
2. Click **Create a Webhook**.
3. **Name**: `AI QA Generator`
4. **URL**: Paste your ngrok URL and append `/api/v1/jira/webhook`
   *   Example: `https://a1b2-c3d4.ngrok-free.app/api/v1/jira/webhook`
5. **Events**:
   *   Under **Issue**, check **created**.
6. **JQL Filter** (Recommended):
   *   `issuetype = Story`
   *   *(This ensures we only trigger for Stories, not bugs or tasks)*
7. Click **Create**.

## Step 5: Test It!
1. Create a new Story in your Jira project.
2. Watch your terminal where `uvicorn` is running.
3. You should see:
   `Received webhook for new story: PROJ-XX. Triggering pipeline.`
   
## note
If you restart ngrok, the URL **will change** (unless you have a paid plan). You will need to update the URL in Jira each time.
