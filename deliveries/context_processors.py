def dmts_context(request):
    unread = 0
    if getattr(request, "user", None) is not None and request.user.is_authenticated:
        unread = request.user.notifications.filter(is_read=False).count()
    return {"unread_notifications": unread}
