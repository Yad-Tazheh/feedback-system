from .models import Conversation


def is_expert(user):
    """
    Returns True if the user is authenticated and belongs to the 'experts' group.
    Caches the result on the user instance to avoid redundant queries.
    """
    if not user or not user.is_authenticated:
        return False
    if hasattr(user, '_is_expert_cache'):
        return user._is_expert_cache
    val = user.groups.filter(name='experts').exists()
    user._is_expert_cache = val
    return val


def can_view(user, conversation):
    """
    Access rules:
    - Staff can view everything.
    - Owner can view their own conversations.
    - An expert can view conversations in the waiting_expert queue and conversations assigned to them.
    - Everyone else is denied.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    if conversation.owner_id is not None and conversation.owner_id == user.id:
        return True
    if is_expert(user):
        if conversation.expert_id == user.id:
            return True
        if conversation.status == Conversation.Status.WAITING_EXPERT:
            return True
    return False


def can_post(user, conversation):
    """
    Posting rules:
    - Closed conversations reject all new messages.
    - Owner can post if the conversation is not closed.
    - Assigned expert can post if the conversation is expert_active.
    - Everyone else is denied.
    """
    if not user or not user.is_authenticated:
        return False
    if conversation.status == Conversation.Status.CLOSED:
        return False
    if conversation.owner_id is not None and conversation.owner_id == user.id:
        return True
    if conversation.expert_id == user.id and conversation.status == Conversation.Status.EXPERT_ACTIVE and is_expert(user):
        return True
    return False


def can_claim(user, conversation):
    """
    Claim rules:
    - User must be an expert.
    - Owner cannot claim their own conversation.
    - Conversation must be in waiting_expert status.
    - Conversation must not already have an assigned expert.
    """
    if not user or not user.is_authenticated:
        return False
    if conversation.owner_id is not None and conversation.owner_id == user.id:
        return False
    if conversation.status != Conversation.Status.WAITING_EXPERT:
        return False
    if conversation.expert_id is not None:
        return False
    if not is_expert(user):
        return False
    return True


def can_release(user, conversation):
    """
    Release rules:
    - Conversation must be in expert_active status.
    - Only the assigned expert can release back to AI.
    """
    if not user or not user.is_authenticated:
        return False
    if conversation.status != Conversation.Status.EXPERT_ACTIVE:
        return False
    if conversation.expert_id == user.id and is_expert(user):
        return True
    return False


def can_close(user, conversation):
    """
    Close rules:
    - Conversation must not already be closed.
    - Staff can close any open conversation.
    - Assigned expert can close conversations assigned to them.
    - Everyone else is denied.
    """
    if not user or not user.is_authenticated:
        return False
    if conversation.status == Conversation.Status.CLOSED:
        return False
    if user.is_staff:
        return True
    if conversation.expert_id == user.id and is_expert(user):
        return True
    return False


def can_request_expert(user, conversation):
    """
    Request expert rules:
    - Conversation must be in 'ai' status.
    - Only the conversation owner can request an expert.
    """
    if not user or not user.is_authenticated:
        return False
    if conversation.owner_id is not None and conversation.owner_id == user.id and conversation.status == Conversation.Status.AI:
        return True
    return False
