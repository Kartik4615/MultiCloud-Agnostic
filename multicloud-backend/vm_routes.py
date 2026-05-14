from flask import Blueprint, request, jsonify

vm_bp = Blueprint("vm", __name__)

# ─── Helper ──────────────────────────────────────────────────────────────────
def err(msg, details=None):
    payload = {"error": msg}
    if details:
        payload["details"] = str(details)
    return jsonify(payload), 400


# ═══════════════════════════════════════════════════════════════════════════════
#  AWS
# ═══════════════════════════════════════════════════════════════════════════════
def _ec2(body):
    import boto3
    return boto3.client(
        "ec2",
        region_name=body.get("region", "us-east-1"),
        aws_access_key_id=body["access_key"],
        aws_secret_access_key=body["secret_key"],
    )

def _parse_aws(i):
    return {
        "id":         i["InstanceId"],
        "name":       next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "—"),
        "type":       i["InstanceType"],
        "state":      i["State"]["Name"],
        "public_ip":  i.get("PublicIpAddress", "—"),
        "private_ip": i.get("PrivateIpAddress", "—"),
        "az":         i["Placement"]["AvailabilityZone"],
        "launched":   str(i.get("LaunchTime", "")),
    }

@vm_bp.route("/api/aws/vms/list", methods=["POST"])
def aws_list():
    body = request.json or {}
    if not body.get("access_key") or not body.get("secret_key"):
        return err("access_key and secret_key are required")
    try:
        ec2  = _ec2(body)
        resp = ec2.describe_instances()
        vms  = [_parse_aws(i) for r in resp["Reservations"] for i in r["Instances"]]
        return jsonify({"provider": "aws", "vms": vms})
    except Exception as e:
        return err("AWS error", e)

@vm_bp.route("/api/aws/vms/create", methods=["POST"])
def aws_create():
    body = request.json or {}
    for f in ["access_key", "secret_key", "region", "instance_type", "ami"]:
        if not body.get(f):
            return err(f"Missing field: {f}")
    try:
        ec2    = _ec2(body)
        kwargs = dict(
            ImageId=body["ami"],
            InstanceType=body["instance_type"],
            MinCount=1, MaxCount=1,
            TagSpecifications=[{"ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": body.get("name", "MultiCloud-VM")}]}],
        )
        if body.get("key_name"):    kwargs["KeyName"]          = body["key_name"]
        if body.get("subnet_id"):   kwargs["SubnetId"]         = body["subnet_id"]
        resp = ec2.run_instances(**kwargs)
        inst = resp["Instances"][0]
        return jsonify({"provider": "aws", "instance_id": inst["InstanceId"],
                        "state": inst["State"]["Name"]})
    except Exception as e:
        return err("AWS create error", e)

@vm_bp.route("/api/aws/vms/action", methods=["POST"])
def aws_action():
    body   = request.json or {}
    action = body.get("action")
    if not body.get("instance_id"):      return err("instance_id is required")
    if action not in ("start","stop","reboot","terminate"):
        return err("action must be start | stop | reboot | terminate")
    try:
        ec2 = _ec2(body)
        ids = [body["instance_id"]]
        if   action == "start":     ec2.start_instances(InstanceIds=ids)
        elif action == "stop":      ec2.stop_instances(InstanceIds=ids)
        elif action == "reboot":    ec2.reboot_instances(InstanceIds=ids)
        elif action == "terminate": ec2.terminate_instances(InstanceIds=ids)
        return jsonify({"provider": "aws", "action": action,
                        "instance_id": body["instance_id"], "status": "ok"})
    except Exception as e:
        return err("AWS action error", e)


# ═══════════════════════════════════════════════════════════════════════════════
#  AZURE
# ═══════════════════════════════════════════════════════════════════════════════
def _azure(body):
    from azure.identity import ClientSecretCredential
    from azure.mgmt.compute import ComputeManagementClient
    cred = ClientSecretCredential(
        tenant_id=body["tenant_id"],
        client_id=body["client_id"],
        client_secret=body["client_secret"],
    )
    return ComputeManagementClient(cred, body["subscription_id"])

def _parse_azure(vm):
    try:
        ps    = vm.instance_view.statuses if vm.instance_view else []
        state = next((s.display_status for s in ps if s.code.startswith("PowerState")), "unknown")
        state = state.lower().replace("vm ", "")
    except Exception:
        state = "unknown"
    try:
        vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else "—"
    except Exception:
        vm_size = "—"
    try:
        os_type = str(vm.storage_profile.os_disk.os_type) if vm.storage_profile else "—"
    except Exception:
        os_type = "—"
    return {
        "id":       vm.id or "—",
        "name":     vm.name or "—",
        "type":     vm_size,
        "state":    state,
        "location": vm.location or "—",
        "os":       os_type,
    }

@vm_bp.route("/api/azure/vms/list", methods=["POST"])
def azure_list():
    body = request.json or {}
    for f in ["tenant_id","client_id","client_secret","subscription_id"]:
        if not body.get(f): return err(f"Missing field: {f}")
    try:
        compute = _azure(body)
        vms     = list(compute.virtual_machines.list_all(expand="instanceView"))
        return jsonify({"provider": "azure", "vms": [_parse_azure(v) for v in vms]})
    except Exception as e:
        import traceback
        print("=" * 60)
        print("AZURE LIST ERROR:")
        print(traceback.format_exc())
        print("=" * 60)
        return err("Azure error", e)

@vm_bp.route("/api/azure/vms/action", methods=["POST"])
def azure_action():
    body   = request.json or {}
    action = body.get("action")
    for f in ["tenant_id","client_id","client_secret","subscription_id","resource_group","vm_name"]:
        if not body.get(f): return err(f"Missing field: {f}")
    if action not in ("start","stop","restart","delete"):
        return err("action must be start | stop | restart | delete")
    try:
        compute = _azure(body)
        rg, name = body["resource_group"], body["vm_name"]
        if   action == "start":   compute.virtual_machines.begin_start(rg, name).result()
        elif action == "stop":    compute.virtual_machines.begin_deallocate(rg, name).result()
        elif action == "restart": compute.virtual_machines.begin_restart(rg, name).result()
        elif action == "delete":  compute.virtual_machines.begin_delete(rg, name).result()
        return jsonify({"provider": "azure", "action": action, "vm_name": name, "status": "ok"})
    except Exception as e:
        return err("Azure action error", e)

@vm_bp.route("/api/azure/vms/create", methods=["POST"])
def azure_create():
    body = request.json or {}
    for f in ["tenant_id","client_id","client_secret","subscription_id",
              "resource_group","location","vm_name","vm_size",
              "admin_username","admin_password","nic_id"]:
        if not body.get(f): return err(f"Missing field: {f}")
    try:
        from azure.mgmt.compute.models import (
            VirtualMachine, HardwareProfile, StorageProfile, OSDisk,
            ImageReference, OSProfile, NetworkProfile,
            NetworkInterfaceReference, DiskCreateOptionTypes
        )
        compute = _azure(body)
        rg, loc, name = body["resource_group"], body["location"], body["vm_name"]
        vm_params = VirtualMachine(
            location=loc,
            hardware_profile=HardwareProfile(vm_size=body["vm_size"]),
            storage_profile=StorageProfile(
                image_reference=ImageReference(
                    publisher=body.get("image_publisher","Canonical"),
                    offer=body.get("image_offer","0001-com-ubuntu-server-jammy"),
                    sku=body.get("image_sku","22_04-lts-gen2"),
                    version="latest",
                ),
                os_disk=OSDisk(create_option=DiskCreateOptionTypes.FROM_IMAGE,
                               name=f"{name}-osdisk"),
            ),
            os_profile=OSProfile(computer_name=name,
                                 admin_username=body["admin_username"],
                                 admin_password=body["admin_password"]),
            network_profile=NetworkProfile(
                network_interfaces=[NetworkInterfaceReference(id=body["nic_id"], primary=True)]
            ),
        )
        result = compute.virtual_machines.begin_create_or_update(rg, name, vm_params).result()
        return jsonify({"provider": "azure", "vm_name": result.name,
                        "location": result.location, "status": "created"})
    except Exception as e:
        import traceback
        print("=" * 60)
        print("AZURE CREATE ERROR:")
        print(traceback.format_exc())
        print("=" * 60)
        return err("Azure create error", e)



# ═══════════════════════════════════════════════════════════════════════════════
#  GCP  (pure REST API — no google-cloud-compute library needed)
# ═══════════════════════════════════════════════════════════════════════════════
def _gcp_token(sa):
    import json, time, base64
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.backends import default_backend
    except ImportError:
        raise Exception("Run: pip install cryptography")
    now     = int(time.time())
    header  = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","typ":"JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(json.dumps({
        "iss":   sa["client_email"],
        "scope": "https://www.googleapis.com/auth/cloud-platform",
        "aud":   "https://oauth2.googleapis.com/token",
        "iat":   now, "exp": now + 3600
    }).encode()).rstrip(b"=")
    msg = header + b"." + payload
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None, backend=default_backend())
    sig = base64.urlsafe_b64encode(key.sign(msg, padding.PKCS1v15(), hashes.SHA256())).rstrip(b"=")
    jwt = (msg + b"." + sig).decode()
    import urllib.request, urllib.parse
    data = urllib.parse.urlencode({"grant_type":"urn:ietf:params:oauth:grant-type:jwt-bearer","assertion":jwt}).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["access_token"]

def _gcp_request(token, method, url, body=None):
    import json, urllib.request, urllib.error
    data    = json.dumps(body).encode() if body else None
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req     = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise Exception(json.loads(e.read()).get("error",{}).get("message", str(e)))

def _parse_gcp_item(inst):
    status_map = {"RUNNING":"running","STOPPED":"stopped","TERMINATED":"terminated",
                  "STAGING":"starting","STOPPING":"stopping","PROVISIONING":"provisioning"}
    ext_ips = [ac.get("natIP") for ni in inst.get("networkInterfaces",[])
               for ac in ni.get("accessConfigs",[]) if ac.get("natIP")]
    return {
        "id":        inst.get("id","—"),
        "name":      inst.get("name","—"),
        "type":      inst.get("machineType","—").split("/")[-1],
        "state":     status_map.get(inst.get("status",""), inst.get("status","unknown").lower()),
        "zone":      inst.get("zone","—").split("/")[-1],
        "public_ip": ext_ips[0] if ext_ips else "—",
    }

@vm_bp.route("/api/gcp/vms/list", methods=["POST"])
def gcp_list():
    import json as _json
    body = request.json or {}
    if not body.get("service_account_json") or not body.get("project_id"):
        return err("service_account_json and project_id are required")
    try:
        sa = body["service_account_json"]
        if isinstance(sa, str): sa = _json.loads(sa)
        token   = _gcp_token(sa)
        project = body["project_id"]
        url     = f"https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/instances"
        data    = _gcp_request(token, "GET", url)
        vms = [_parse_gcp_item(i) for zd in data.get("items",{}).values() for i in zd.get("instances",[])]
        return jsonify({"provider": "gcp", "vms": vms})
    except Exception as e:
        import traceback; print("="*60); print("GCP LIST ERROR:"); print(traceback.format_exc()); print("="*60)
        return err("GCP error", str(e))

@vm_bp.route("/api/gcp/vms/create", methods=["POST"])
def gcp_create():
    import json as _json
    body = request.json or {}
    for f in ["service_account_json","project_id","zone","vm_name","machine_type"]:
        if not body.get(f): return err(f"Missing field: {f}")
    try:
        sa = body["service_account_json"]
        if isinstance(sa, str): sa = _json.loads(sa)
        token   = _gcp_token(sa)
        project = body["project_id"]
        zone    = body["zone"]
        url     = f"https://compute.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances"
        payload = {
            "name": body["vm_name"],
            "machineType": f"zones/{zone}/machineTypes/{body['machine_type']}",
            "disks": [{"boot":True,"autoDelete":True,"initializeParams":{
                "sourceImage": body.get("disk_image","projects/debian-cloud/global/images/family/debian-11"),
                "diskSizeGb":  str(body.get("disk_size_gb",10))}}],
            "networkInterfaces": [{"network":"global/networks/default",
                "accessConfigs":[{"name":"External NAT","type":"ONE_TO_ONE_NAT"}]}]
        }
        _gcp_request(token, "POST", url, payload)
        return jsonify({"provider":"gcp","vm_name":body["vm_name"],"zone":zone,"status":"created"})
    except Exception as e:
        import traceback; print(traceback.format_exc())
        return err("GCP create error", str(e))

@vm_bp.route("/api/gcp/vms/action", methods=["POST"])
def gcp_action():
    import json as _json
    body = request.json or {}
    action = body.get("action")
    for f in ["service_account_json","project_id","zone","vm_name"]:
        if not body.get(f): return err(f"Missing field: {f}")
    if action not in ("start","stop","reset","delete"):
        return err("action must be start | stop | reset | delete")
    try:
        sa = body["service_account_json"]
        if isinstance(sa, str): sa = _json.loads(sa)
        token   = _gcp_token(sa)
        project = body["project_id"]
        zone    = body["zone"]
        name    = body["vm_name"]
        if action == "delete":
            url = f"https://compute.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances/{name}"
            _gcp_request(token, "DELETE", url)
        else:
            url = f"https://compute.googleapis.com/compute/v1/projects/{project}/zones/{zone}/instances/{name}/{action}"
            _gcp_request(token, "POST", url)
        return jsonify({"provider":"gcp","action":action,"vm_name":name,"status":"ok"})
    except Exception as e:
        return err("GCP action error", str(e))

# ─── Health check ─────────────────────────────────────────────────────────────
@vm_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "MultiCloud VM Manager"})
