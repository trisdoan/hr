from odoo import Command
from odoo.tests.common import (
    new_test_user,
)
from odoo.tools import convert_file

from .test_governance_circle import TestGovernanceCircle

DATA_FILES = ["tests/governance_circle_data.xml"]


class TestPermission(TestGovernanceCircle):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.load_data()
        cls.users = cls._create_test_users()
        cls.james = cls.users["james"]
        cls.kevin = cls.users["kevin"]
        cls.bob = cls.users["bob"]

        cls.memory_role = cls.env.ref(
            "hr_governance.memory_gct", raise_if_not_found=False
        )
        cls.memory_role.enable_edit_circle = True
        cls.steering_role = cls.env.ref(
            "hr_governance.steering_gct", raise_if_not_found=False
        )
        cls.facilitation_role = cls.env.ref(
            "hr_governance.facilitation_gct", raise_if_not_found=False
        )

    @classmethod
    def load_data(cls):
        """Load test data files."""
        for filename in DATA_FILES:
            convert_file(
                cls.env,
                module="hr_governance",
                filename=filename,
                idref={},
                mode="init",
                noupdate=False,
                kind="test",
            )

    @classmethod
    def _create_test_users(cls):
        """Create test users with employees."""
        users_data = [
            {"login": "james", "name": "James"},
            {"login": "kevin", "name": "Kevin"},
            {"login": "bob", "name": "Bob"},
        ]

        users = {}
        for data in users_data:
            user = new_test_user(
                cls.env,
                login=data["login"],
                groups="base.group_user,hr_governance.governance_group_user",
                name=data["name"],
            )
            cls.env["hr.employee"].create({"name": data["name"], "user_id": user.id})
            users[data["login"]] = user.with_user(user)
        return users

    def _assign_role(self, circle, role, user):
        """Assign a role to a user in a circle."""
        role_in_circle = circle.child_ids.filtered_domain([("type_id", "=", role.id)])
        role_in_circle.write(
            {"member_rel_ids": [Command.create({"member_id": user.employee_id.id})]}
        )

    def _assert_edit_access(self, circles, user, expected=True):
        """Assert that user has edit access to circles."""
        accessible_ids = set(user.allowed_edit_governance_ids.ids)
        circle_ids = [circles.id] if hasattr(circles, "id") else [c.id for c in circles]

        if expected:
            self.assertTrue(set(circle_ids).issubset(accessible_ids))
        else:
            self.assertFalse(any(cid in accessible_ids for cid in circle_ids))

    def _assert_children_edit_access(self, circle, user, expected=True):
        """Assert that user has edit access to circle's children."""
        child_ids = set(circle.child_ids.ids)
        accessible_ids = set(user.allowed_edit_governance_ids.ids)

        if expected:
            self.assertTrue(child_ids.issubset(accessible_ids))
        else:
            self.assertFalse(child_ids.issubset(accessible_ids))

    def _create_circle(self, name, parent_id=None):
        """Create a governance circle with given name and parent."""
        if parent_id is None:
            parent_id = self.env.ref("hr_governance.root").id

        return (
            self.env["governance.circle"]
            .with_context(default_is_circle=True)
            .create(
                {
                    "name": name,
                    "parent_id": parent_id,
                }
            )
        )

    def test_01(self):
        """The Steering Role is Assigned Within the Circle"""
        test_circle = self._create_circle("Test Circle")
        self._assign_role(test_circle, self.memory_role, self.james)
        self._assign_role(test_circle, self.facilitation_role, self.bob)

        self.env.invalidate_all()
        self._assert_edit_access(test_circle, self.james, False)
        self._assert_children_edit_access(test_circle, self.james, False)

        self._assert_edit_access(test_circle, self.bob, False)
        self._assert_children_edit_access(test_circle, self.bob, False)

        # Steering is assigned
        self._assign_role(test_circle, self.steering_role, self.kevin)
        self.env.invalidate_all()

        # as Memory is still assigned, steering is not allowed
        self._assert_edit_access(test_circle, self.kevin, False)
        self._assert_children_edit_access(test_circle, self.kevin, False)

        # Un-assign Memory
        test_circle.child_ids.filtered_domain(
            [("type_id", "=", self.memory_role.id)]
        ).member_rel_ids.unlink()
        self.env.invalidate_all()

        # as Memory is un-assigned, steering is allowed_edit_governance_ids
        self._assert_edit_access(test_circle, self.kevin)
        self._assert_children_edit_access(test_circle, self.kevin)

        self._assert_edit_access(test_circle, self.james, False)
        self.assertFalse(self.james.allowed_edit_governance_ids)

    def test_02(self):
        """Neither "Memory" nor "Steering" Roles Are Assigned in the Circle,
        but the Parent Circle Has a "Memory"/Steering Role"""
        circle = self._create_circle("Circle")
        self._assign_role(circle, self.memory_role, self.james)

        subcircle = self._create_circle("SubCircle", circle.id)
        self._assign_role(subcircle, self.facilitation_role, self.bob)
        self.env.invalidate_all()

        self._assert_edit_access(circle | subcircle, self.james)
        self._assert_children_edit_access(circle, self.james)

        self._assert_edit_access(circle | subcircle, self.bob, False)
        self._assert_children_edit_access(subcircle, self.bob, False)

        # circle has both Memory and Steering assigned,
        # only Memory is allowed to update subcircle
        self._assign_role(circle, self.steering_role, self.kevin)
        self.env.invalidate_all()
        self._assert_edit_access(circle | subcircle, self.james)
        self._assert_children_edit_access(circle, self.james)

        self._assert_edit_access(circle | subcircle, self.kevin, False)

    def test_03(self):
        """Neither "Memory" nor "Steering" Roles Are Assigned in the Circle
        or in the Parent Circle"""
        circle = self._create_circle("Circle")
        self._assign_role(circle, self.facilitation_role, self.james)

        subcircle = self._create_circle("SubCircle", circle.id)
        self._assign_role(subcircle, self.facilitation_role, self.bob)
        self.env.invalidate_all()

        self._assert_edit_access(circle | subcircle, self.james, False)
        self._assert_children_edit_access(circle, self.james, False)

        self._assert_edit_access(circle | subcircle, self.bob, False)
        self._assert_children_edit_access(subcircle, self.bob, False)

    def test_04(self):
        """Complex Inheritance Chain Across Multiple Levels"""
        circle_level_1 = self._create_circle("Circle level 1")
        self._assign_role(circle_level_1, self.memory_role, self.james)

        circle_level_2 = self._create_circle("Circle level 2", circle_level_1.id)
        self._assign_role(circle_level_2, self.steering_role, self.kevin)

        circle_level_3 = self._create_circle("Circle level 3", circle_level_2.id)
        self._assign_role(circle_level_3, self.facilitation_role, self.bob)
        self.env.invalidate_all()

        # For Circle level 1
        self._assert_edit_access(circle_level_1, self.james)
        self.assertNotIn(
            circle_level_1.id,
            self.kevin.allowed_edit_governance_ids.ids
            + self.bob.allowed_edit_governance_ids.ids,
        )

        # For Circle level 2
        self._assert_edit_access(circle_level_2, self.kevin)

        # as circle_level_2 is assigned, james cannot touch it and its subcircles
        self._assert_edit_access(circle_level_2, self.james, False)
        self.assertNotIn(
            circle_level_2.child_ids.ids, self.james.allowed_edit_governance_ids.ids
        )

        # For Circle level 3
        self._assert_edit_access(circle_level_3, self.kevin)
        self._assert_edit_access(
            circle_level_3 | circle_level_3.child_ids, self.james, False
        )
        self._assert_edit_access(circle_level_3, self.bob, False)
        self._assert_children_edit_access(circle_level_3, self.bob, False)
