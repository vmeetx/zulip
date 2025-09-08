# Redmine webhook integration

Easily receive notifications in Zulip whenever issues are created or updated in
your Redmine projects. This integration uses the
[suer/redmine_webhook](https://github.com/suer/redmine_webhook  ) plugin for
Redmine.

## Setup

1. **Create a Bot:** Create an incoming webhook bot named "Redmine" or similar.
   Note its API key.
2. **Configure Redmine Webhook:**
   *   Install the [suer/redmine_webhook](https://github.com/suer/redmine_webhook  )
       plugin in your Redmine instance.
   *   Go to **Administration** > **Settings** > **Webhooks** in your Redmine.
   *   Add a new webhook.
   *   Set the **URL** to:
       `https://yourZulipDomain.com/api/v1/external/redmine?api_key=yourRedmineBotApiKey`
       (Replace `yourZulipDomain.com` with your Zulip server's hostname and
       `yourRedmineBotApiKey` with the API key from step 1).
   *   Select the events you want to receive notifications for (e.g., Issue
       Created, Issue Updated).
   *   Save the webhook configuration.

## URL format
  https://yourZulipDomain.com/api/v1/external/redmine?api_key=yourRedmineBotApiKey 

*   `yourZulipDomain.com`: Your Zulip server's hostname.
*   `yourRedmineBotApiKey`: The API key of your Redmine bot.

## Parameters

You can customize where notifications are sent by adding parameters to the URL:

*   `&stream=channel-name`: Sends notifications to the specified stream.
*   `&topic=custom-topic`: Sets a custom topic for notifications (URL-encode if
    it contains spaces).
*   `&only_events=["opened"]`: Only sends notifications for issue
    creation.
*   `&exclude_events=["updated"]`: Does not send notifications for issue
    updates.

**Example (send to "redmine" stream, "notifications" topic, only new issues):**
 https://yourZulipDomain.com/api/v1/external/redmine?api_key=yourRedmineBotApiKey&stream=redmine&topic=notifications&only_events=["opened"] 


## Example messages

**Issue Created:**
> **Topic:** `ProjectName #123: Fix login bug`
>
> Veer created issue [#123: Fix login bug](http://redmine.example.com/issues/123) with status **New** and priority **High**.
> > Users are unable to log in using the latest build. Investigate authentication module.

**Issue Updated:**
> **Topic:** `ProjectName #123: Fix login bug`
>
> Jane updated issue [#123: Fix login bug](http://redmine.example.com/issues/123).
> > Added patch for auth module. Ready for review.

## Behavior notes

*   Messages are sent to the bot's owner via direct message by default. Use the
    `stream` parameter to send to a specific channel.
*   Topics are automatically set to `{Project Name} #{Issue ID}: {Issue Subject}`
    to group conversations about the same issue.
*   Supports `only_events` and `exclude_events` filtering using `opened`
    and `updated`.

## Related articles

*   [Zulip incoming webhooks overview]( https://zulip.com/api/incoming-webhooks-overview  )
*   [Zulip API keys](https://zulip.com/api/api-keys  )



