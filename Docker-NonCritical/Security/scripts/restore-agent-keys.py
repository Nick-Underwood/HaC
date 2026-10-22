#!/usr/bin/env python3
"""Restore Wazuh agent rows into global.db from client.keys.

After a volume wipe (version-bump deploy), the fresh global.db has no agent rows.
wazuh-db only persists agents whose rows exist; without them every keepalive
fails with "assigning the groups ... agent not found" and the console shows no
agents. This script rebuilds the rows (id, name, ip, key, default group) from
the restored /var/ossec/etc/client.keys file. Idempotent — run any time.
"""
import sqlite3
import time

DB = "/var/ossec/queue/db/global.db"
KEYS = "/var/ossec/etc/client.keys"
GROUP_ID = 1  # 'default' group

def main():
    db = sqlite3.connect(DB)
    now = int(time.time())
    restored = 0
    for line in open(KEYS, encoding="utf-8"):
        parts = line.split()
        if len(parts) < 4:
            continue
        aid, name, ip, key = parts[0], parts[1], parts[2], parts[3]
        if db.execute("select id from agent where id=?", (aid,)).fetchone():
            continue
        db.execute(
            "insert into agent (id,name,ip,register_ip,internal_key,manager_host,"
            'node_name,date_add,last_keepalive,"group",group_sync_status,'
            "sync_status,connection_status,group_config_status,status_code) "
            "values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, name, ip, ip, key, "wazuh.manager", "node01", now, now,
             "default", "synced", "synced", "active", "synced", 0),
        )
        db.execute(
            "insert or ignore into belongs (id_agent,id_group,priority) values (?,?,0)",
            (aid, GROUP_ID),
        )
        restored += 1
        print(f"restored agent {aid} ({name})")
    db.commit()
    db.close()
    print(f"done: {restored} agent(s) restored; total in db: "
          f"{len([r for r in sqlite3.connect(DB).execute('select id from agent')])}")

if __name__ == "__main__":
    main()
