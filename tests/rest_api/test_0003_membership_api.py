# Copyright (C) 2021 Intel Corporation
#
# SPDX-License-Identifier: MIT

import json
import os.path as osp
from http import HTTPStatus

import pytest
from deepdiff import DeepDiff

from .utils.config import ASSETS_DIR, get_method, patch_method

@pytest.fixture(scope='module')
def memberships():
    with open(osp.join(ASSETS_DIR, 'memberships.json')) as f:
        return json.load(f)['results']

@pytest.fixture(scope='module')
def roles(memberships):
    data = {}
    for membership in memberships:
        org = membership['organization']
        role = membership['role']
        data.setdefault(org, {}).setdefault(role, []).append({
            'username': membership['user']['username'],
            'id': membership['id']
        })
    return data

class TestGetMembership:
    def _test_can_see_memberships(self, user, data, **kwargs):
        response = get_method(user, 'memberships', **kwargs)

        assert response.status_code == HTTPStatus.OK
        assert DeepDiff(data, response.json()['results']) == {}

    def _test_cannot_see_memberships(self, user, **kwargs):
        response = get_method(user, 'memberships', **kwargs)

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_admin_can_see_all_memberships(self, memberships):
        self._test_can_see_memberships('admin2', memberships, page_size='all')

    def test_non_admin_can_see_only_self_memberships(self, memberships):
        non_admins= ['business1', 'user1', 'dummy1','worker2']
        for user in non_admins:
            data = [m for m in memberships if m['user']['username'] == user]
            self._test_can_see_memberships(user, data)

    def test_all_members_can_see_other_members_membership(self, memberships):
        data = [m for m in memberships if m['organization'] == 1]
        for membership in data:
            self._test_can_see_memberships(membership['user']['username'],
                data, org_id=1)

    def test_non_members_cannot_see_members_membership(self):
        non_org1_users = ['user2', 'worker3']
        for user in non_org1_users:
            self._test_cannot_see_memberships(user, org_id=1)


class TestPatchMembership:
    _ORG = 2

    def _test_can_change_membership(self, user, membership_id, new_role):
        response = patch_method(user, f"memberships/{membership_id}",
            {'role': new_role}, org_id=self._ORG)

        assert response.status_code == HTTPStatus.OK
        assert response.json()['role'] == new_role

    def _test_cannot_change_membership(self, user, membership_id, new_role):
        response = patch_method(user, f"memberships/{membership_id}",
            {'role': new_role}, org_id=self._ORG)

        assert response.status_code == HTTPStatus.FORBIDDEN

    @pytest.mark.parametrize("who, whom, new_role, is_allow", [
        ('supervisor', 'worker',     'supervisor', False),
        ('supervisor', 'maintainer', 'supervisor', False),
        ('worker',     'supervisor', 'worker',     False),
        ('worker',     'maintainer', 'worker',     False),
        ('maintainer', 'maintainer', 'worker',     False),
        ('maintainer', 'supervisor', 'worker',     True),
        ('maintainer', 'worker',     'supervisor', True),
        ('owner',      'supervisor', 'worker',     True),
        ('owner',      'worker',     'supervisor', True),
        ('owner',      'maintainer', 'worker',     True),
    ])
    def test_user_can_change_role_of_member(self, who, whom, new_role, is_allow, roles):
        user = roles[self._ORG][who][0]['username']
        membership_id = roles[self._ORG][whom][1]['id']

        if is_allow:
            self._test_can_change_membership(user, membership_id, new_role)
        else:
            self._test_cannot_change_membership(user, membership_id, new_role)