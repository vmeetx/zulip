import logging
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string, check_none_or, check_int
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

logger = logging.getLogger(__name__)

REDMINE_EVENT_TYPES = [
    "opened",
    "updated",
]

def get_issue_id(payload: WildValue) -> str:
    try:
        return str(payload["issue"]["id"].tame(check_int))
    except Exception as e:
        logger.warning(f"Failed to get issue ID: {e}")
        return "unknown"

def get_issue_subject(payload: WildValue) -> str:
    try:
        return payload["issue"]["subject"].tame(check_string)
    except Exception as e:
        logger.warning(f"Failed to get issue subject: {e}")
        return "No subject"

def get_project_name(payload: WildValue) -> str:
    try:
        return payload["issue"]["project"]["name"].tame(check_string)
    except Exception as e:
        logger.warning(f"Failed to get project name: {e}")
        return "Unknown project"

def get_issue_url(payload: WildValue) -> str:
    try:
        url = payload["url"].tame(check_string)
        if url and url.strip() and url != "not yet implemented":
            return url.strip()
    except Exception as e:
        logger.warning(f"Failed to get issue URL: {e}")
    return ""

def get_user_full_name(user_data: WildValue) -> str:
    try:
        first_name = user_data["firstname"].tame(check_none_or(check_string)) or ""
        last_name = user_data["lastname"].tame(check_none_or(check_string)) or ""
        full_name = f"{first_name} {last_name}".strip()
        if full_name:
            return full_name
    except Exception as e:
        logger.debug(f"Failed to get first/last name: {e}")
    
    try:
        return user_data["login"].tame(check_string)
    except Exception as e:
        logger.debug(f"Failed to get login: {e}")
        return "Unknown user"

def get_formatted_issue_link(payload: WildValue) -> str:
    issue_id = get_issue_id(payload)
    subject = get_issue_subject(payload)
    url = get_issue_url(payload)

    if url:
        return f"[#{issue_id}: {subject}]({url})"
    else:
        return f"#{issue_id}: {subject}"

def get_issue_topic(payload: WildValue) -> str:
    project_name = get_project_name(payload)
    issue_id = get_issue_id(payload)
    subject = get_issue_subject(payload)
    return f"{project_name} #{issue_id}: {subject}"

def handle_opened_event(payload: WildValue) -> str:
    try:
        author_name = get_user_full_name(payload["issue"]["author"])
    except Exception as e:
        logger.warning(f"Failed to get author for opened event: {e}")
        author_name = "Unknown user"
    
    issue_link = get_formatted_issue_link(payload)

    try:
        status = payload["issue"]["status"]["name"].tame(check_string)
    except Exception as e:
        logger.warning(f"Failed to get status: {e}")
        status = "unknown"
    
    try:
        priority = payload["issue"]["priority"]["name"].tame(check_string)
    except Exception as e:
        logger.warning(f"Failed to get priority: {e}")
        priority = "unknown"

    description = None
    try:
        description = payload["issue"]["description"].tame(check_none_or(check_string))
    except Exception as e:
        logger.debug(f"Failed to get description: {e}")

    content = f"{author_name} opened issue {issue_link} with status \"{status}\" and priority \"{priority}\"."

    if description:
        # TODO: Consider truncating very long descriptions
        content += f"\nDescription: {description}"

    return content

def handle_updated_event(payload: WildValue) -> str:
    try:
        author_name = get_user_full_name(payload["journal"]["author"])
    except Exception as e:
        logger.warning(f"Failed to get author for updated event: {e}")
        author_name = "Unknown user"
    
    issue_link = get_formatted_issue_link(payload)
    
    notes = None
    try:
        if "journal" in payload:
            notes = payload["journal"]["notes"].tame(check_none_or(check_string))
    except Exception as e:
        logger.debug(f"Failed to get notes: {e}")

    content = f"{author_name} updated issue {issue_link}."

    if notes:
        # TODO: Consider truncating very long notes or handling formatting
        content += f"\nNotes: {notes}"

    return content

@webhook_view("Redmine", all_event_types=REDMINE_EVENT_TYPES)
@typed_endpoint
def api_redmine_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    try:
        redmine_data = payload["payload"]
    except Exception as e:
        logger.error(f"Failed to extract payload: {e}")
        return json_success(request)
    
    try:
        action = redmine_data["action"].tame(check_string)
    except Exception as e:
        logger.warning(f"Failed to get action: {e}")
        return json_success(request)

    if action not in REDMINE_EVENT_TYPES:
        logger.debug(f"Unsupported action: {action}")
        return json_success(request)

    content: str = ""
    try:
        if action == "opened":
            content = handle_opened_event(redmine_data)
        elif action == "updated":
            content = handle_updated_event(redmine_data)
    except Exception as e:
        logger.error(f"Error handling {action} event: {e}")
        return json_success(request)

    if not content:
        return json_success(request)

    try:
        topic_name = get_issue_topic(redmine_data)
        check_send_webhook_message(
            request, user_profile, topic_name, content, event_type=action
        )
    except Exception as e:
        logger.error(f"Failed to send webhook message: {e}")
        return json_success(request)

    return json_success(request)