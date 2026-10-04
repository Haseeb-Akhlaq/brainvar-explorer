"""Permission classes for the users API."""

from rest_framework.permissions import BasePermission, DjangoModelPermissions


class DjangoModelViewPermissions(DjangoModelPermissions):
    """
    `DjangoModelPermissions`, extended so that reads are gated too.

    DRF's version maps `GET` to an empty permission list — reading is
    deliberately left open, because the common case is a public catalogue that
    only writes need rights for. On a list of user accounts that default is
    wrong in a way that is easy to miss: the endpoint looks protected, passes a
    glance at the decorator, and hands every signed-in visitor the whole table.

    Django has created a `view_<model>` permission for every model since 2.1,
    so requiring it here is the same mechanism, applied to the method that
    actually matters for this resource.
    """

    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        # Preflight and HEAD stay open to authentication alone; neither
        # returns a body, and CORS preflight arrives without credentials.
        "OPTIONS": [],
        "HEAD": [],
    }


class CanChangeUsers(BasePermission):
    """
    Requires `users.change_user`.

    Used for the invitation action. `DjangoModelPermissions` maps every POST
    to `add_user`, which is the wrong question here: sending an invitation
    sets a password and activates an existing account, so it is a change to
    that account, not the creation of one. Someone who may only add users
    should not be able to reset an existing person's credentials.
    """

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.has_perm("users.change_user"))
