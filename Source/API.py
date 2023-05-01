from Entities import Pod
from Logging import Logging
import json
import yaml
from kubernetes import client, config, utils
from kubernetes.client.exceptions import ApiException
from flask import Flask, request, jsonify
from flask_cors import CORS


# Flask API
app = Flask(__name__)
CORS(app)


# Kubernetes API
config.load_incluster_config()
v1 = client.CoreV1Api()
k8s_client = client.ApiClient() 
customAPI = client.CustomObjectsApi()



@app.route('/')
def index():
    return jsonify(code=200, data='Kubernetes Security')

    

@app.route('/api/v1/pods', methods=['GET', 'POST', 'PUT', 'DELETE'])
def interact_pods():
    pod = request.args.get('pod', '')
    namespace = request.args.get('namespace', '')

    if request.method == 'GET':
        try:
            if pod and namespace:
                res = v1.read_namespaced_pod(name=pod, namespace=namespace, _preload_content=False)
                return jsonify(code=200, data=Pod(data=json.loads(res.data)).attributes())
            else:
                res = v1.list_pod_for_all_namespaces(watch=False,  _preload_content=False)
                return jsonify(code=200, data=[Pod(data=item).attributes() for item in json.loads(res.data)['items']])
        except ApiException as e:
            if e.status == 404:
                return jsonify(code=404, data='Not Found')
            else:
                return jsonify(code=500, data='Internal Server Error')
        

    elif request.method == 'POST':
        pass


    elif request.method == 'PUT':
        with open('../Policy/block-traffic.yaml', 'r') as f:
            data = yaml.safe_load(f)
        data['metadata']['namespace'] = namespace
        data['spec']['podSelector']['matchLabels']['app.kubernetes.io/name'] = pod
        with open('../Policy/block-traffic.yaml', 'w') as f:
            yaml.dump(data, f)

        try:
            utils.create_from_yaml(k8s_client, '../Policy/block-traffic.yaml')
            return jsonify(code=200, data='OK')
        except ApiException as e:
            if e.status == 409:
                return jsonify(code=409, data='Conflict')
            else:
                return jsonify(code=500, data='Internal Server Error')
        

    elif request.method == 'DELETE':
        try:
            v1.delete_namespaced_pod(name=pod, namespace=namespace, propagation_policy='Background', grace_period_seconds=0)
            Logging(level='INFO', message=f'Pod {pod} in namespace {namespace} deleted').log()
            return jsonify(code=200, data='OK')
        

        except ApiException as e:
            if e.status == 404:
                return jsonify(code=404, data='Not Found')
            else:
                return jsonify(code=500, data='Internal Server Error')
        

    else:
        return jsonify(code=400, data='Bad Request')



retrieved_data = {}
@app.route('/api/v1/webhook-listener', methods=['GET', 'POST'])
def webhook_listener():
    global retrieved_data
    if request.method == 'GET':
        return jsonify(code=200, data=retrieved_data)
    elif request.method == 'POST':
        retrieved_data = request.json
        # auto_block_traffic()
        return jsonify(code=200, data='OK')
    else:
        return jsonify(code=400, data='Bad Request')
    


def auto_block_traffic(pod: str, namespace: str):
    with open('../Policy/block-traffic.yaml', 'r') as f:
            data = yaml.safe_load(f)
    data['metadata']['namespace'] = namespace
    data['spec']['podSelector']['matchLabels']['app.kubernetes.io/name'] = pod
    with open('../Policy/block-traffic.yaml', 'w') as f:
        yaml.dump(data, f)

    try:
        utils.create_from_yaml(k8s_client, '../Policy/block-traffic.yaml')
        return jsonify(code=200, data='OK')
    except ApiException as e:
        if e.status == 409:
            return jsonify(code=409, data='Conflict')
        else:
            return jsonify(code=500, data='Internal Server Error')
    


@app.route('/api/v1/resources', methods=['GET'])
def get_resource_usage():
    pod = request.args.get('pod', '')
    namespace = request.args.get('namespace', '')

    res = customAPI.list_namespaced_custom_object(group="metrics.k8s.io",version="v1beta1", namespace=namespace, plural="pods")
    if not pod:
        return jsonify(code=200, data=[{'name': item['metadata']['name'], 'namespace': item['metadata']['namespace'],
                                    'cpu': item['containers'][0]['usage']['cpu'], 'memory': item['containers'][0]['usage']['memory']} 
                                    for item in res['items']])
    else:
        return jsonify(code=200, data=[{'name': item['metadata']['name'], 'namespace': item['metadata']['namespace'],
                                    'cpu': item['containers'][0]['usage']['cpu'], 'memory': item['containers'][0]['usage']['memory']} 
                                    for item in res['items'] if item['metadata']['name'] == pod])
    




def main():
    app.run(host='0.0.0.0', port=50000, debug=True)
    
    
        