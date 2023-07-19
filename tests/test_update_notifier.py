from src.update_notifier import UpdateNotifier


def test_package_upgrade():
    UpdateNotifier.DEBUG = True
    un = UpdateNotifier(
        organization="<organization>",
        project="<project>",
        feed_name="<feed_name>",
        package_name="<package_name>",
        username="<username>",
    )
    un.check_for_update()
