from typing import Any

import orjson
from typing_extensions import override

from zerver.actions.channel_folders import (
    check_add_channel_folder,
    do_archive_channel_folder,
    try_reorder_realm_channel_folders,
)
from zerver.actions.streams import do_change_stream_folder, do_deactivate_stream
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import ChannelFolder
from zerver.models.realms import get_realm
from zerver.models.streams import get_stream


class ChannelFoldersTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        zulip_realm = get_realm("zulip")
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        lear_user = self.lear_user("cordelia")

        check_add_channel_folder(
            zulip_realm,
            "Frontend",
            "Channels for frontend discussions",
            acting_user=iago,
        )
        check_add_channel_folder(
            zulip_realm, "Backend", "Channels for **backend** discussions", acting_user=iago
        )
        check_add_channel_folder(
            zulip_realm, "Marketing", "Channels for marketing discussions", acting_user=desdemona
        )
        check_add_channel_folder(
            lear_user.realm, "Devops", "Channels for devops discussions", acting_user=lear_user
        )


class ChannelFolderCreationTest(ZulipTestCase):
    def test_creating_channel_folder(self) -> None:
        self.login("shiva")
        realm = get_realm("zulip")

        params = {"name": "Frontend", "description": ""}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.filter(realm=realm).last()
        assert channel_folder is not None
        self.assertEqual(channel_folder.name, "Frontend")
        self.assertEqual(channel_folder.description, "")
        self.assertEqual(channel_folder.id, channel_folder.order)
        response = orjson.loads(result.content)
        self.assertEqual(response["channel_folder_id"], channel_folder.id)

    def test_creating_channel_folder_with_duplicate_name(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")

        params = {"name": "Frontend", "description": ""}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        self.assertTrue(ChannelFolder.objects.filter(realm=realm, name="Frontend").exists())

        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Channel folder name already in use")

        # Archived folder names can be reused.
        folder = ChannelFolder.objects.get(name="Frontend", realm=realm)
        do_archive_channel_folder(folder, acting_user=self.example_user("iago"))

        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        self.assertTrue(ChannelFolder.objects.filter(realm=realm, name="Frontend").exists())

        # Folder names should be unique case-insensitively.
        params["name"] = "frontEND"
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Channel folder name already in use")

    def test_rendered_description_for_channel_folder(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")

        params = {"name": "Frontend", "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(realm=realm, name="Frontend")
        self.assertEqual(channel_folder.description, "Channels for frontend discussions")
        self.assertEqual(
            channel_folder.rendered_description, "<p>Channels for frontend discussions</p>"
        )

        params = {"name": "Backend", "description": "Channels for **backend** discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(realm=realm, name="Backend")
        self.assertEqual(channel_folder.description, "Channels for **backend** discussions")
        self.assertEqual(
            channel_folder.rendered_description,
            "<p>Channels for <strong>backend</strong> discussions</p>",
        )

    def test_invalid_params_for_channel_folder(self) -> None:
        self.login("iago")

        params = {"name": "", "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Channel folder name can't be empty.")

        invalid_name = "abc\000"
        params = {"name": invalid_name, "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(result, "Invalid character in channel folder name, at position 4.")

        long_name = "a" * (ChannelFolder.MAX_NAME_LENGTH + 1)
        params = {"name": long_name, "description": "Channels for frontend discussions"}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(
            result, f"name is too long (limit: {ChannelFolder.MAX_NAME_LENGTH} characters)"
        )

        long_description = "a" * (ChannelFolder.MAX_DESCRIPTION_LENGTH + 1)
        params = {"name": "Frontend", "description": long_description}
        result = self.client_post("/json/channel_folders/create", params)
        self.assert_json_error(
            result,
            f"description is too long (limit: {ChannelFolder.MAX_DESCRIPTION_LENGTH} characters)",
        )


class GetChannelFoldersTest(ChannelFoldersTestCase):
    def test_get_channel_folders(self) -> None:
        iago = self.example_user("iago")
        desdemona = self.example_user("desdemona")
        zulip_realm = iago.realm
        frontend_folder = ChannelFolder.objects.get(name="Frontend", realm=zulip_realm)
        backend_folder = ChannelFolder.objects.get(name="Backend", realm=zulip_realm)
        marketing_folder = ChannelFolder.objects.get(name="Marketing", realm=zulip_realm)

        def check_channel_folders_in_zulip_realm(
            channel_folders: list[dict[str, Any]], marketing_folder_included: bool = True
        ) -> None:
            if marketing_folder_included:
                self.assert_length(channel_folders, 3)
            else:
                self.assert_length(channel_folders, 2)

            self.assertEqual(channel_folders[0]["id"], frontend_folder.id)
            self.assertEqual(channel_folders[0]["name"], "Frontend")
            self.assertEqual(channel_folders[0]["description"], "Channels for frontend discussions")
            self.assertEqual(
                channel_folders[0]["rendered_description"],
                "<p>Channels for frontend discussions</p>",
            )
            self.assertEqual(channel_folders[0]["is_archived"], frontend_folder.is_archived)
            self.assertEqual(channel_folders[0]["creator_id"], iago.id)

            self.assertEqual(channel_folders[1]["id"], backend_folder.id)
            self.assertEqual(channel_folders[1]["name"], "Backend")
            self.assertEqual(
                channel_folders[1]["description"], "Channels for **backend** discussions"
            )
            self.assertEqual(
                channel_folders[1]["rendered_description"],
                "<p>Channels for <strong>backend</strong> discussions</p>",
            )
            self.assertEqual(channel_folders[1]["is_archived"], backend_folder.is_archived)
            self.assertEqual(channel_folders[1]["creator_id"], iago.id)

            if marketing_folder_included:
                self.assertEqual(channel_folders[2]["id"], marketing_folder.id)
                self.assertEqual(channel_folders[2]["name"], "Marketing")
                self.assertEqual(
                    channel_folders[2]["description"], "Channels for marketing discussions"
                )
                self.assertEqual(
                    channel_folders[2]["rendered_description"],
                    "<p>Channels for marketing discussions</p>",
                )
                self.assertEqual(channel_folders[2]["is_archived"], marketing_folder.is_archived)
                self.assertEqual(channel_folders[2]["creator_id"], desdemona.id)

        self.login("iago")
        result = self.client_get("/json/channel_folders")
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        check_channel_folders_in_zulip_realm(channel_folders_data)

        # Check member user can also see all channel folders.
        self.login("hamlet")
        result = self.client_get("/json/channel_folders")
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        check_channel_folders_in_zulip_realm(channel_folders_data)

        # Check guest can also see all channel folders.
        self.login("polonius")
        result = self.client_get("/json/channel_folders")
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        check_channel_folders_in_zulip_realm(channel_folders_data)

        marketing_folder.is_archived = True
        marketing_folder.save()

        result = self.client_get("/json/channel_folders")
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        check_channel_folders_in_zulip_realm(channel_folders_data, False)

        result = self.client_get(
            "/json/channel_folders", {"include_archived": orjson.dumps(True).decode()}
        )
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        check_channel_folders_in_zulip_realm(channel_folders_data)

    def test_get_channel_folders_according_to_order(self) -> None:
        iago = self.example_user("iago")
        realm = iago.realm
        self.login_user(iago)

        result = self.client_get("/json/channel_folders")
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        channel_folders_names = [item["name"] for item in channel_folders_data]
        self.assertEqual(channel_folders_names, ["Frontend", "Backend", "Marketing"])

        try_reorder_realm_channel_folders(
            realm, list(reversed([item["id"] for item in channel_folders_data]))
        )
        result = self.client_get("/json/channel_folders")
        channel_folders_data = orjson.loads(result.content)["channel_folders"]
        channel_folders_names = [item["name"] for item in channel_folders_data]
        self.assertEqual(channel_folders_names, ["Marketing", "Backend", "Frontend"])


class UpdateChannelFoldersTest(ChannelFoldersTestCase):
    def test_updating_channel_folder_name(self) -> None:
        realm = get_realm("zulip")
        channel_folder = ChannelFolder.objects.get(name="Frontend", realm=realm)
        channel_folder_id = channel_folder.id

        self.login("hamlet")

        params = {"name": "Web frontend"}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")

        # Test invalid channel folder ID.
        result = self.client_patch("/json/channel_folders/999", params)
        self.assert_json_error(result, "Invalid channel folder ID")

        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id)
        self.assertEqual(channel_folder.name, "Web frontend")

        params = {"name": ""}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Channel folder name can't be empty.")

        params = {"name": "Backend"}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Channel folder name already in use")

        # Folder names should be unique case-insensitively.
        params = {"name": "backEND"}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Channel folder name already in use")

        invalid_name = "abc\000"
        params = {"name": invalid_name}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Invalid character in channel folder name, at position 4.")

        long_name = "a" * (ChannelFolder.MAX_NAME_LENGTH + 1)
        params = {"name": long_name}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(
            result, f"name is too long (limit: {ChannelFolder.MAX_NAME_LENGTH} characters)"
        )

    def test_updating_channel_folder_description(self) -> None:
        channel_folder = ChannelFolder.objects.get(name="Frontend", realm=get_realm("zulip"))
        channel_folder_id = channel_folder.id

        self.login("hamlet")

        params = {"description": "Channels for **frontend** discussions"}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")

        # Test invalid channel folder ID.
        result = self.client_patch("/json/channel_folders/999", params)
        self.assert_json_error(result, "Invalid channel folder ID")

        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id)
        self.assertEqual(channel_folder.description, "Channels for **frontend** discussions")
        self.assertEqual(
            channel_folder.rendered_description,
            "<p>Channels for <strong>frontend</strong> discussions</p>",
        )

        # Channel folder descriptions can be empty.
        params = {"description": ""}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id)
        self.assertEqual(channel_folder.description, "")
        self.assertEqual(channel_folder.rendered_description, "")

        params = {"description": "a" * (ChannelFolder.MAX_DESCRIPTION_LENGTH + 1)}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(
            result,
            f"description is too long (limit: {ChannelFolder.MAX_DESCRIPTION_LENGTH} characters)",
        )

    def test_archiving_and_unarchiving_channel_folder(self) -> None:
        desdemona = self.example_user("desdemona")
        realm = get_realm("zulip")
        channel_folder = ChannelFolder.objects.get(name="Frontend", realm=realm)
        channel_folder_id = channel_folder.id

        self.login("hamlet")

        params = {"is_archived": orjson.dumps(True).decode()}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(result, "Must be an organization administrator")

        self.login("iago")

        # Test invalid channel folder ID.
        result = self.client_patch("/json/channel_folders/999", params)
        self.assert_json_error(result, "Invalid channel folder ID")

        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id)
        self.assertTrue(channel_folder.is_archived)

        params = {"is_archived": orjson.dumps(False).decode()}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id)
        self.assertFalse(channel_folder.is_archived)

        # Folder containing channels cannot be archived.
        stream = get_stream("Verona", realm)
        do_change_stream_folder(stream, channel_folder, acting_user=desdemona)
        params = {"is_archived": orjson.dumps(True).decode()}
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(
            result, "You need to remove all the channels from this folder to archive it."
        )

        do_deactivate_stream(stream, acting_user=desdemona)
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_error(
            result, "You need to remove all the channels from this folder to archive it."
        )

        do_change_stream_folder(stream, None, acting_user=desdemona)
        result = self.client_patch(f"/json/channel_folders/{channel_folder_id}", params)
        self.assert_json_success(result)
        channel_folder = ChannelFolder.objects.get(id=channel_folder_id)
        self.assertTrue(channel_folder.is_archived)


class ReorderChannelFolderTest(ChannelFoldersTestCase):
    def test_reorder(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        order = list(
            ChannelFolder.objects.filter(realm=realm)
            .order_by("-order")
            .values_list("order", flat=True)
        )
        result = self.client_patch(
            "/json/channel_folders", info={"order": orjson.dumps(order).decode()}
        )
        self.assert_json_success(result)
        fields = ChannelFolder.objects.filter(realm=realm).order_by("order")
        for field in fields:
            self.assertEqual(field.id, order[field.order])

    def test_reorder_duplicates(self) -> None:
        self.login("iago")
        realm = get_realm("zulip")
        order = list(
            ChannelFolder.objects.filter(realm=realm)
            .order_by("-order")
            .values_list("order", flat=True)
        )
        frontend_folder = ChannelFolder.objects.get(name="Frontend", realm=realm)
        order.append(frontend_folder.id)
        result = self.client_patch(
            "/json/channel_folders", info={"order": orjson.dumps(order).decode()}
        )
        self.assert_json_success(result)
        fields = ChannelFolder.objects.filter(realm=realm).order_by("order")
        for field in fields:
            self.assertEqual(field.id, order[field.order])

    def test_reorder_unauthorized(self) -> None:
        self.login("hamlet")
        realm = get_realm("zulip")
        order = list(
            ChannelFolder.objects.filter(realm=realm)
            .order_by("-order")
            .values_list("order", flat=True)
        )
        result = self.client_patch(
            "/json/channel_folders", info={"order": orjson.dumps(order).decode()}
        )
        self.assert_json_error(result, "Must be an organization administrator")

    def test_reorder_invalid(self) -> None:
        self.login("iago")
        order = [100, 200, 300]
        result = self.client_patch(
            "/json/channel_folders", info={"order": orjson.dumps(order).decode()}
        )
        self.assert_json_error(result, "Invalid order mapping.")
        order = [1, 2]
        result = self.client_patch(
            "/json/channel_folders", info={"order": orjson.dumps(order).decode()}
        )
        self.assert_json_error(result, "Invalid order mapping.")
