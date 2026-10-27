import json, os

BASE = "C:/Dev/infra/hac/development/task-automation/n8n/workflows/"

# ---- shared dead-letter nodes (Error Trigger -> Vikunja "Sync Errors") ----
build_js = """const ej = $json;
const msg = (ej.error && ej.error.message) ? ej.error.message : (ej.message || 'Unknown error');
const desc = ['Workflow: ' + (ej.workflow && ej.workflow.name || 'unknown'), 'Error: ' + msg, '', 'Raw: ' + JSON.stringify(ej).slice(0,4000)].join('\\n');
return [{ title: '[SYNC ERROR] ' + (ej.workflow && ej.workflow.name || 'n8n'), description: desc, project_id: Number($env.VIKUNJA_ERROR_PROJECT_ID) }];"""

def deadletter_nodes(wf):
    max_y = max(n["position"][1] for n in wf["nodes"])
    y = max_y + 320
    err = {"parameters": {}, "id": "catch_errors", "name": "Catch Errors",
           "type": "n8n-nodes-base.errorTrigger", "typeVersion": 1, "position": [240, y]}
    build = {"parameters": {"mode": "runOnceForEachItem", "jsCode": build_js},
             "id": "build_error_task", "name": "Build Error Task",
             "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [500, y]}
    log = {"parameters": {"method": "POST", "url": "={{$env.VIKUNJA_URL + '/api/v1/tasks'}}",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "Authorization", "value": "={{'Bearer ' + $env.VIKUNJA_API_TOKEN}}"},
                {"name": "Content-Type", "value": "application/json"}]},
            "sendBody": True, "specifyBody": "json", "jsonBody": "={{$json}}"},
            "id": "log_sync_errors", "name": "Log to Sync Errors",
            "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [760, y]}
    return [err, build, log]

def add_deadletter(wf):
    wf["nodes"].extend(deadletter_nodes(wf))
    wf.setdefault("connections", {})
    wf["connections"]["Catch Errors"] = {"main": [[{"node": "Build Error Task", "type": "main", "index": 0}]]}
    wf["connections"]["Build Error Task"] = {"main": [[{"node": "Log to Sync Errors", "type": "main", "index": 0}]]}
    return wf

# ---- 1) MS To Do <-> Vikunja ----
p1 = BASE + "ms-todo_vikunja_bidirectional.json"
wf1 = json.load(open(p1, encoding="utf-8"))
add_deadletter(wf1)
json.dump(wf1, open(p1, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("hardened ms-todo_vikunja_bidirectional.json")

# ---- 2) Vikunja <-> Forgejo (fix missing FORGEJO_SYNC_REPO default) ----
p2 = BASE + "vikunja_forgejo_selective_sync.json"
wf2 = json.load(open(p2, encoding="utf-8"))
add_deadletter(wf2)
# patch the Forgejo pull URL to default the missing env var
for n in wf2["nodes"]:
    if n["name"] == "Get Forgejo Issues":
        old = n["parameters"]["url"]
        if "FORGEJO_SYNC_REPO" in old and "||" not in old:
            n["parameters"]["url"] = old.replace(
                "$env.FORGEJO_SYNC_REPO",
                "($env.FORGEJO_SYNC_REPO || 'hac')")
            print("patched Forgejo pull URL -> default 'hac'")
json.dump(wf2, open(p2, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("hardened vikunja_forgejo_selective_sync.json")

# ---- 3) Vikunja -> Outline (collectionId + title prefix + fix field name) ----
p3 = BASE + "vikunja_outline_autodoc.json"
wf3 = json.load(open(p3, encoding="utf-8"))
add_deadletter(wf3)
for n in wf3["nodes"]:
    if n["name"] == "Build Outline Doc":
        old = n["parameters"]["jsCode"]
        new = old.replace(
            "return [{ title: t.title, body, template, vikunjaTaskId: t.id }];",
            "const prefix = (template || 'doc');\nreturn [{ title: prefix + ' - ' + t.title, text: body, collectionId: $env.OUTLINE_COLLECTION_ID, vikunjaTaskId: t.id }];")
        assert new != old, "build_doc patch did not apply"
        n["parameters"]["jsCode"] = new
        print("patched Build Outline Doc (title prefix + collectionId + text field)")
    if n["name"] == "Write Back Doc Link":
        old = n["parameters"].get("jsonBody", "")
        if "$json.url" in old:
            n["parameters"]["jsonBody"] = old.replace("$json.url", "($json.data && $json.data.url) || $json.url")
            print("patched Write Back Doc Link url ref (Outline data wrap)")
json.dump(wf3, open(p3, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
print("hardened vikunja_outline_autodoc.json")
print("ALL HARDENED")
