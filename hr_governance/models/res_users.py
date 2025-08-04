# Copyright 2025 Camptocamp
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, fields, models


class Users(models.Model):
    _inherit = "res.users"

    allowed_edit_governance_ids = fields.Many2many(
        "governance.circle",
        compute="_compute_allowed_edit_governance_ids",
    )

    def _compute_allowed_edit_governance_ids(self):
        """
        Write access rules:
        - User can edit circles where they have edit-enabled roles
        - If no edit-enabled roles, user can edit circles where they have steering roles
        - Steering roles act as fallback when no edit-enabled roles are assigned
        """
        for user in self:
            user_assigned_roles = self._get_user_assigned_roles(user.id)
            if not user_assigned_roles:
                user.allowed_edit_governance_ids = [Command.clear()]
                continue

            circle_hierarchy_cache = self._build_circle_hierarchy_cache(
                user_assigned_roles
            )

            # Get editable circles from edit-capable roles
            edit_capable_roles = user_assigned_roles.filtered_domain(
                [("type_id.enable_edit_circle", "=", True)]
            )
            editable_circles = self.env[
                "governance.circle"
            ].get_circles_editable_by_edit_roles(
                user.id, edit_capable_roles, circle_hierarchy_cache
            )

            # fallback access
            steering_capable_roles = user_assigned_roles.filtered_domain(
                [("type_id.is_steering_role", "=", True)]
            )
            editable_circles |= self.env[
                "governance.circle"
            ].get_circles_editable_by_steering_roles(
                steering_capable_roles, circle_hierarchy_cache
            )

            # Set the computed field
            user.allowed_edit_governance_ids = [Command.clear()] + [
                Command.link(circle.id) for circle in editable_circles
            ]

    def _build_circle_hierarchy_cache(self, user_assigned_roles):
        """Build a cache of circle hierarchy records for each user role to avoid repeated queries."""
        circle_hierarchy_cache = {}
        for role in user_assigned_roles:
            parent_circle = role.parent_id
            circle_hierarchy_cache[role.id] = parent_circle.get_hierarchy_records(
                include_self=True
            ).filtered_domain([("is_circle", "=", True)])
        return circle_hierarchy_cache

    def _get_user_assigned_roles(self, user_id):
        """Get all roles assigned to the user across all governance circles."""
        return self.env["governance.circle"].search(
            [("member_rel_ids.member_id.user_id", "=", user_id)]
        )
