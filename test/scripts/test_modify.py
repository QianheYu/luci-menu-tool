import json
import sys

# Load export
with open('/tmp/test_nft_qos.json', 'r') as f:
    data = json.load(f)

# Modify luci-app-nft-qos root order
pkg = data.get('luci-app-nft-qos')
if pkg:
    for tree in pkg.get('menu_trees', []):
        if tree.get('root_path') == 'admin/services/nft-qos':
            tree['root_new_order'] = '71'
            break

# Save modified
with open('/tmp/test_nft_qos_modified.json', 'w') as f:
    json.dump(data, f, indent=2)

print("Modified luci-app-nft-qos root order to 71")
