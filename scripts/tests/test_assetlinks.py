"""The Digital Asset Links file that verifies the Android app's link handling.

Android checks it once at install: a typo here and every mergers.fyi link opens
in the browser again, with nothing failing anywhere to say so.
"""

import json
import re

from scripts.paths import REPO_ROOT

ASSETLINKS = REPO_ROOT / "frontend" / "public" / ".well-known" / "assetlinks.json"

# The release key's certificate (CN=mergers.fyi sideload), as in the app's
# signed APKs. Changing the key needs a new entry here before the new APK ships.
RELEASE_KEY = "C2:B7:7A:94:83:8E:1B:3D:EE:F9:77:74:38:8B:C7:ED:27:73:8B:61:A6:7A:10:4E:3F:A6:0D:4C:24:8B:AC:28"


def test_assetlinks_names_the_app_and_its_key():
    statements = json.loads(ASSETLINKS.read_text())
    by_package = {s["target"]["package_name"]: s for s in statements}
    assert set(by_package) == {"fyi.mergers.app", "fyi.mergers.app.debug"}
    for statement in statements:
        assert statement["relation"] == ["delegate_permission/common.handle_all_urls"]
        assert statement["target"]["namespace"] == "android_app"
        fingerprints = statement["target"]["sha256_cert_fingerprints"]
        assert RELEASE_KEY in fingerprints
        for fp in fingerprints:
            assert re.fullmatch(r"(?:[0-9A-F]{2}:){31}[0-9A-F]{2}", fp)
