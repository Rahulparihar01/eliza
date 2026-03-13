# Agent Configuration Guide

A simple guide to configuring AI agents in your platform.

---

## Overview

AI agents are the intelligent assistants that help answer questions, analyze data, and generate insights. This guide shows you how to configure them to use the right AI models and settings for your needs.

---

## Quick Start

### What You Can Configure

For each agent, you can customize:

- **Prompts** - What the agent's role and goals are
- **AI Model** - Which AI model to use (GPT-4, Claude, etc.)
- **Temperature** - How creative vs. focused the agent should be
- **Tools** - Which data sources the agent can access
- **Account** - Which API account to bill usage to (if you have multiple)

### Where to Configure Agents

1. Go to **Admin Settings** > **Agent Configuration**
2. Select a flow (e.g., "Data Analysis Flow")
3. Click on an agent to edit its settings
4. Make your changes and click **Save**

Changes take effect **immediately** - no restart required!

---

## Step-by-Step: Configuring an Agent

### Step 1: Navigate to Agent Configuration

```
Main Menu → Admin Settings → Agent Configuration
```

You'll see a list of your flows and agents.

### Step 2: Select an Agent

Click on the agent you want to configure. For example:

- **Data Analysis Flow**
  - Data Retrieval Agent
  - Business Intelligence Analyst

### Step 3: Configure Agent Settings

#### **Agent Prompts**

Define what the agent does:

- **Role**: A short description of the agent's job
  - Example: "Data Retrieval Specialist"
  
- **Goal**: What the agent is trying to accomplish
  - Example: "Find all relevant data from databases and documents"
  
- **Backstory**: Additional context about the agent's expertise
  - Example: "You are an expert at querying databases and searching through documents to find the most relevant information."

#### **AI Model Settings**

Choose which AI model to use:

- **Model**: Pick from available models
  - `gpt-4` - Most capable, higher cost (recommended for analysis)
  - `gpt-3.5-turbo` - Faster, lower cost (good for retrieval)
  - `claude-3-opus` - Anthropic's most capable model
  - `claude-3-sonnet` - Balanced performance and cost

- **Temperature**: Controls creativity (0.0 - 1.0)
  - `0.0-0.3` - Focused, consistent (best for data tasks)
  - `0.4-0.7` - Balanced
  - `0.8-1.0` - Creative, varied responses

- **Max Tokens**: Maximum response length
  - `1000-2000` - Short responses
  - `2000-4000` - Standard responses (recommended)
  - `4000-8000` - Long, detailed responses

#### **Tools**

Select which tools the agent can use:

- ☑ **HR Database Tool** - Query employee data
- ☑ **Document Search Tool** - Search uploaded documents
- ☐ **Web Search Tool** - Search the internet

### Step 4: Save Configuration

Click **Save** to apply your changes. The new configuration will be used for all future executions.

---

## Multiple API Accounts

If you have multiple API accounts for the same provider (e.g., separate development and production OpenAI keys), you'll see an **Account** selector when configuring agents.

### When This Appears

You'll only see the account selector if:
- You've configured multiple API accounts for the same provider
- Multiple accounts support the model you've selected

### How to Choose

The system will show you:

```
Account: [OpenAI Production ▼]
  • OpenAI Production (sk-...456) - 10,000 TPM
  • OpenAI Development (sk-...123) - 1,000 TPM
  • OpenAI Budget (sk-...789) - 500 TPM
```

**What to consider:**
- **Rate limits** - Higher limits for production workloads
- **Billing** - Different accounts may bill to different departments
- **Purpose** - Use development keys for testing, production keys for live use

**Most of the time**, the system will automatically pick the best account, so you won't need to choose manually.

---

## Setting Up AI Provider Accounts

Before you can configure agents, you need to set up at least one AI provider account.

### Step 1: Go to Provider Configuration

```
Main Menu → Admin Settings → AI Model Providers → Add Provider
```

### Step 2: Fill in Provider Details

#### **Configuration Name** (Required)

Give this configuration a memorable name:

- ✅ Good: "OpenAI Production Account"
- ✅ Good: "OpenAI Development"
- ❌ Avoid: "Config 1" or "OpenAI" (not descriptive)

**Tip:** Use names that indicate the purpose or environment.

#### **Provider Type** (Required)

Select the AI provider:
- **OpenAI** - GPT-4, GPT-3.5
- **Anthropic** - Claude models
- **AWS Bedrock** - Multiple providers through AWS
- **Groq** - Fast inference

#### **API Key** (Required)

Paste your API key from the provider's dashboard.

**Where to find API keys:**
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys
- Groq: https://console.groq.com/keys

#### **Available Models**

Check which models this account can access:
- ☑ gpt-4
- ☑ gpt-4-turbo
- ☑ gpt-3.5-turbo

#### **Priority** (Optional)

If you have multiple accounts for the same provider, set priority:
- `1` = Highest priority (used first)
- `2` = Medium priority
- `3` = Lowest priority (used as fallback)

**When priority matters:**
- The system will automatically use the highest-priority account that supports the model
- Lower-priority accounts are used as backups if the primary fails

#### **Rate Limit** (Optional)

Set the requests-per-minute limit for this account:
- Use the limit from your API provider's dashboard
- Prevents hitting rate limit errors
- Default: 60 requests/minute

### Step 3: Test Connection

Click **Test Connection** to verify your API key works.

✅ **Success**: "Connection healthy - gpt-4 responded correctly"
❌ **Failed**: Check your API key and try again

### Step 4: Save Provider

Click **Save** to add this provider. You can now use it in agent configurations.

---

## Best Practices

### Temperature Settings

| Task Type | Recommended Temperature | Why |
|-----------|------------------------|-----|
| Data retrieval | 0.1 - 0.3 | Need consistent, factual responses |
| Data analysis | 0.3 - 0.5 | Balance between accuracy and insight |
| Report writing | 0.5 - 0.7 | More natural, varied language |
| Creative tasks | 0.7 - 0.9 | Maximum variety and creativity |

### Model Selection

| Agent Type | Recommended Model | Why |
|------------|------------------|-----|
| Data Retrieval | gpt-3.5-turbo | Fast, cost-effective for simple queries |
| Analysis | gpt-4 | Better reasoning for complex analysis |
| Report Generation | gpt-4 or claude-3-opus | High-quality writing |
| Simple Q&A | gpt-3.5-turbo | Sufficient for straightforward questions |

### Multiple API Accounts

**When to use multiple accounts:**
- Separate billing for different teams/projects
- Different rate limits (dev vs. production)
- Testing with lower-cost keys before production
- Redundancy (automatic failover if one key fails)

**Naming convention:**
- `[Provider] [Environment/Purpose]`
- Examples:
  - "OpenAI Production"
  - "OpenAI Development"
  - "OpenAI HR Team"
  - "Anthropic Testing"

---

## Testing Your Configuration

### Step 1: Configure Agent

Make your changes to the agent configuration.

### Step 2: Click "Test Agent"

The system will run a test query using your new configuration.

### Step 3: Review Results

Check the test results:
- ✅ **Success**: Agent responded correctly with your settings
- ❌ **Failed**: Review error message and adjust settings

**Common issues:**
- Model not available → Check that your API account supports this model
- Rate limit exceeded → Wait a moment and try again
- Invalid API key → Verify your API key in Provider Settings

---

## Frequently Asked Questions

### Do I need to restart anything after changing agent configuration?

**No!** Changes take effect immediately for all new executions. Any in-progress tasks will complete with the old configuration, but new tasks will use your updated settings.

### Can I use different models for different agents?

**Yes!** Each agent can use a completely different model and settings. For example:
- Data Retrieval Agent → gpt-3.5-turbo (fast, cheap)
- Analysis Agent → gpt-4 (smart, thorough)

### What happens if I have multiple API keys for the same provider?

The system will:
1. **Automatically select** the highest-priority account that supports your chosen model
2. **Prompt you** to choose if you're using a model that multiple accounts support
3. **Show you** clear account names and rate limits to help you decide

### Can I see which API account was used for a specific query?

**Yes!** Check the Execution Timeline for any question. It shows:
- Which agent executed
- Which model was used
- Which API account was used
- How long it took
- What tools were called

### How do I know which models my API account supports?

When you create or edit a provider configuration, you can:
1. Check the **Available Models** list
2. Use the **Discover Models** button (for some providers like AWS Bedrock)
3. Check your provider's dashboard (OpenAI, Anthropic, etc.)

### What if I delete an API account that agents are using?

The system prevents you from deleting accounts that are in use. You'll see:
```
Cannot delete: This account is used by 3 agents.
Please update agent configurations first.
```

### Can I change an agent's configuration while it's running?

**Yes**, but the change won't affect that specific execution. The running task will complete with the old configuration, and the next task will use the new settings.

---

## Troubleshooting

### "No provider configured for model X"

**Problem:** You've selected a model, but no API account supports it.

**Solution:**
1. Go to Admin Settings > AI Model Providers
2. Check your existing providers - do any support this model?
3. If not, add or edit a provider to include this model
4. Go back to agent configuration and try again

### "Rate limit exceeded"

**Problem:** You're making too many requests to the AI provider.

**Solution:**
1. Wait a few minutes and try again
2. Check your provider's dashboard for current usage
3. In Provider Settings, verify your rate limit is set correctly
4. Consider upgrading your API plan with the provider
5. If you have multiple accounts, the system will automatically try the next-priority account

### "Invalid API key"

**Problem:** The API key is incorrect or has been revoked.

**Solution:**
1. Go to Admin Settings > AI Model Providers
2. Find the configuration with the invalid key
3. Click **Edit**
4. Paste a new, valid API key from your provider's dashboard
5. Click **Test Connection** to verify
6. Click **Save**

### Agent responses are too generic

**Try:**
- Increase temperature to 0.5-0.7
- Make the agent's Goal and Backstory more specific
- Use a more capable model (gpt-4 instead of gpt-3.5-turbo)

### Agent responses are inconsistent

**Try:**
- Decrease temperature to 0.1-0.3
- Make the agent's prompts more explicit about expected behavior
- Add more specific tools instead of relying on general reasoning

### Agent takes too long to respond

**Try:**
- Use a faster model (gpt-3.5-turbo instead of gpt-4)
- Reduce max_tokens if responses are too long
- Reduce the number of tools enabled
- Check if your API account has rate limiting delays

---

## Need Help?

If you're stuck or have questions not covered here:

1. Check the **Execution Timeline** for detailed error messages
2. Test your API keys using the **Test Connection** button in Provider Settings
3. Try the **Test Agent** button to see if your configuration works
4. Contact your system administrator for platform-specific issues

---

## Summary Checklist

### Setting Up (One Time)

- [ ] Add at least one AI provider account (Admin Settings > AI Model Providers)
- [ ] Test the connection to verify your API key works
- [ ] Configure which models are available

### Configuring Agents (Per Agent)

- [ ] Set agent prompts (Role, Goal, Backstory)
- [ ] Choose AI model
- [ ] Set temperature (0.3 for data tasks, 0.7 for creative tasks)
- [ ] Set max tokens (2000-4000 is usually good)
- [ ] Enable/disable tools as needed
- [ ] (Optional) Choose specific API account if you have multiple
- [ ] Test your configuration
- [ ] Save changes

### Ongoing

- [ ] Monitor execution timelines to see how agents perform
- [ ] Adjust temperature if responses are too generic or inconsistent
- [ ] Switch models if cost or performance needs change
- [ ] Add new API accounts as your needs grow

---

**Remember:** Changes take effect immediately - no restart needed! 🚀

