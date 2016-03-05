from __future__ import unicode_literals

import datetime
from moto.core import BaseBackend
from moto.core.utils import iso_8601_datetime_with_milliseconds
from .utils import create_id


class Deployment(dict):
    def __init__(self, deployment_id, name):
        super(Deployment, self).__init__()
        self['id'] = deployment_id
        self['stageName'] = name


class IntegrationResponse(dict):
    def __init__(self, status_code, selection_pattern=None):
        self['responseTemplates'] = {"application/json": None}
        self['statusCode'] = status_code
        if selection_pattern:
            self['selectionPattern'] = selection_pattern


class Integration(dict):
    def __init__(self, integration_type, uri, http_method):
        super(Integration, self).__init__()
        self['type'] = integration_type
        self['uri'] = uri
        self['httpMethod'] = http_method
        self["integrationResponses"] = {
            "200": IntegrationResponse(200)
        }

    def create_integration_response(self, status_code, selection_pattern):
        integration_response = IntegrationResponse(status_code, selection_pattern)
        self["integrationResponses"][status_code] = integration_response
        return integration_response

    def get_integration_response(self, status_code):
        return self["integrationResponses"][status_code]

    def delete_integration_response(self, status_code):
        return self["integrationResponses"].pop(status_code)


class MethodResponse(dict):
    def __init__(self, status_code):
        super(MethodResponse, self).__init__()
        self['statusCode'] = status_code


class Method(dict):
    def __init__(self, method_type, authorization_type):
        super(Method, self).__init__()
        self.update(dict(
            httpMethod=method_type,
            authorizationType=authorization_type,
            authorizerId=None,
            apiKeyRequired=None,
            requestParameters=None,
            requestModels=None,
            methodIntegration=None,
        ))
        self.method_responses = {}

    def create_response(self, response_code):
        method_response = MethodResponse(response_code)
        self.method_responses[response_code] = method_response
        return method_response

    def get_response(self, response_code):
        return self.method_responses[response_code]

    def delete_response(self, response_code):
        return self.method_responses.pop(response_code)


class Resource(object):
    def __init__(self, id, path_part, parent_id):
        self.id = id
        self.path_part = path_part
        self.parent_id = parent_id
        self.resource_methods = {
            'GET': {}
        }

    def to_dict(self):
        response = {
            "path": self.path_part,
            "id": self.id,
            "resourceMethods": self.resource_methods,
        }
        if self.parent_id:
            response['parent_id'] = self.parent_id
        return response

    def add_method(self, method_type, authorization_type):
        method = Method(method_type=method_type, authorization_type=authorization_type)
        self.resource_methods[method_type] = method
        return method

    def get_method(self, method_type):
        return self.resource_methods[method_type]

    def add_integration(self, method_type, integration_type, uri):
        integration = Integration(integration_type, uri, method_type)
        self.resource_methods[method_type]['methodIntegration'] = integration
        return integration

    def get_integration(self, method_type):
        return self.resource_methods[method_type]['methodIntegration']

    def delete_integration(self, method_type):
        return self.resource_methods[method_type].pop('methodIntegration')


class RestAPI(object):
    def __init__(self, id, name, description):
        self.id = id
        self.name = name
        self.description = description
        self.create_date = datetime.datetime.utcnow()

        self.deployments = {}

        self.resources = {}
        self.add_child('/')  # Add default child

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "createdDate": iso_8601_datetime_with_milliseconds(self.create_date),
        }

    def add_child(self, path, parent_id=None):
        child_id = create_id()
        child = Resource(id=child_id, path_part=path, parent_id=parent_id)
        self.resources[child_id] = child
        return child

    def create_deployment(self, name):
        deployment_id = create_id()
        deployment = Deployment(deployment_id, name)
        self.deployments[deployment_id] = deployment
        return deployment

    def get_deployment(self, deployment_id):
        return self.deployments[deployment_id]

    def get_deployments(self):
        return self.deployments.values()

    def delete_deployment(self, deployment_id):
        return self.deployments.pop(deployment_id)


class APIGatewayBackend(BaseBackend):
    def __init__(self, region_name):
        super(APIGatewayBackend, self).__init__()
        self.apis = {}
        self.region_name = region_name

    def reset(self):
        region_name = self.region_name
        self.__dict__ = {}
        self.__init__(region_name)

    def create_rest_api(self, name, description):
        api_id = create_id()
        rest_api = RestAPI(api_id, name, description)
        self.apis[api_id] = rest_api
        return rest_api

    def get_rest_api(self, function_id):
        rest_api = self.apis[function_id]
        return rest_api

    def list_apis(self):
        return self.apis.values()

    def delete_rest_api(self, function_id):
        rest_api = self.apis.pop(function_id)
        return rest_api

    def list_resources(self, function_id):
        api = self.get_rest_api(function_id)
        return api.resources.values()

    def get_resource(self, function_id, resource_id):
        api = self.get_rest_api(function_id)
        resource = api.resources[resource_id]
        return resource

    def create_resource(self, function_id, parent_resource_id, path_part):
        api = self.get_rest_api(function_id)
        child = api.add_child(
            path=path_part,
            parent_id=parent_resource_id,
        )
        return child

    def delete_resource(self, function_id, resource_id):
        api = self.get_rest_api(function_id)
        resource = api.resources.pop(resource_id)
        return resource

    def get_method(self, function_id, resource_id, method_type):
        resource = self.get_resource(function_id, resource_id)
        return resource.get_method(method_type)

    def create_method(self, function_id, resource_id, method_type, authorization_type):
        resource = self.get_resource(function_id, resource_id)
        method = resource.add_method(method_type, authorization_type)
        return method

    def get_method_response(self, function_id, resource_id, method_type, response_code):
        method = self.get_method(function_id, resource_id, method_type)
        method_response = method.get_response(response_code)
        return method_response

    def create_method_response(self, function_id, resource_id, method_type, response_code):
        method = self.get_method(function_id, resource_id, method_type)
        method_response = method.create_response(response_code)
        return method_response

    def delete_method_response(self, function_id, resource_id, method_type, response_code):
        method = self.get_method(function_id, resource_id, method_type)
        method_response = method.delete_response(response_code)
        return method_response

    def create_integration(self, function_id, resource_id, method_type, integration_type, uri):
        resource = self.get_resource(function_id, resource_id)
        integration = resource.add_integration(method_type, integration_type, uri)
        return integration

    def get_integration(self, function_id, resource_id, method_type):
        resource = self.get_resource(function_id, resource_id)
        return resource.get_integration(method_type)

    def delete_integration(self, function_id, resource_id, method_type):
        resource = self.get_resource(function_id, resource_id)
        return resource.delete_integration(method_type)

    def create_integration_response(self, function_id, resource_id, method_type, status_code, selection_pattern):
        integration = self.get_integration(function_id, resource_id, method_type)
        integration_response = integration.create_integration_response(status_code, selection_pattern)
        return integration_response

    def get_integration_response(self, function_id, resource_id, method_type, status_code):
        integration = self.get_integration(function_id, resource_id, method_type)
        integration_response = integration.get_integration_response(status_code)
        return integration_response

    def delete_integration_response(self, function_id, resource_id, method_type, status_code):
        integration = self.get_integration(function_id, resource_id, method_type)
        integration_response = integration.delete_integration_response(status_code)
        return integration_response

    def create_deployment(self, function_id, name):
        api = self.get_rest_api(function_id)
        deployment = api.create_deployment(name)
        return deployment

    def get_deployment(self, function_id, deployment_id):
        api = self.get_rest_api(function_id)
        return api.get_deployment(deployment_id)

    def get_deployments(self, function_id):
        api = self.get_rest_api(function_id)
        return api.get_deployments()

    def delete_deployment(self, function_id, deployment_id):
        api = self.get_rest_api(function_id)
        return api.delete_deployment(deployment_id)

apigateway_backends = {}
for region_name in ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-northeast-1']:  # Not available in boto yet
    apigateway_backends[region_name] = APIGatewayBackend(region_name)
