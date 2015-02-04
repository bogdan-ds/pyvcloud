# VMware vCloud Python SDK
# Copyright (c) 2014 VMware, Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# coding: utf-8

import time
import base64
import requests
from StringIO import StringIO
import json
from xml.etree import ElementTree as ET
from pyvcloud.schema.vcd.v1_5.schemas.admin import vCloudEntities
from pyvcloud.schema.vcd.v1_5.schemas.admin.vCloudEntities import AdminCatalogType
from pyvcloud.schema.vcd.v1_5.schemas.vcloud import sessionType, organizationType, organizationListType
from pyvcloud.vcloudsession import VCS
from pyvcloud.vapp import VAPP
from pyvcloud.gateway import Gateway
from pyvcloud.schema.vcim import serviceType, vchsType
from schema.vcd.v1_5.schemas.vcloud import networkType, vdcType, queryRecordViewType, taskType, vAppType, organizationType, catalogType, diskType, vmsType, vcloudType, catalogItemType, mediaType
# from schema.vcd.v1_5.schemas.vcloud.catalogItemType import CatalogItemType

class VCA(object):

    def __init__(self, host, username, service_type='ondemand', version='5.7', verify=True):
        if not (host.startswith('https://') or host.startswith('http://')):
            host = 'https://' + host
        self.host = host
        self.username = username
        self.token = None
        self.service_type = service_type
        self.version = version
        self.verify = verify
        self.vcloud_session = None
        self.instances = None
        self.org = None
        self.organization = None
        self.vdc = None
        self.services = None
        
    def login(self, password=None, token=None, org=None, org_url=None):
        """
        Request to login to vCloud Air
        
        :param password: The password.
        :param token: The token from a previous successful login, None if this is a new login request.                        
        :return: True if the user was successfully logged in, False otherwise.
        """
                    
        if self.service_type == 'subscription':
            if token:
                headers = {}
                headers["x-vchs-authorization"] = token
                headers["Accept"] = "application/xml;version=" + self.version
                response = requests.get(self.host + "/api/vchs/services", headers=headers, verify=self.verify)
                if response.status_code == requests.codes.ok:
                    self.services = serviceType.parseString(response.content, True)
                    self.token = token
                    return True
                else:
                    return False
            else:
                url = self.host + "/api/vchs/sessions"
                encode = "Basic " + base64.standard_b64encode(self.username + ":" + password)
                headers = {}
                headers["Authorization"] = encode.rstrip()
                headers["Accept"] = "application/xml;version=" + self.version
                response = requests.post(url, headers=headers, verify=self.verify)
                if response.status_code == requests.codes.created:
                    self.token = response.headers["x-vchs-authorization"]
                    return True
                else:
                    return False
        elif self.service_type == 'ondemand':
            if token:
                self.token = token
                self.instances = self.get_instances()
                return self.instances != None
            else:
                url = self.host + "/api/iam/login"
                encode = "Basic " + base64.standard_b64encode(self.username + ":" + password)
                headers = {}
                headers["Authorization"] = encode.rstrip()
                headers["Accept"] = "application/json;version=%s" % self.version
                response = requests.post(url, headers=headers, verify=self.verify)
                if response.status_code == requests.codes.created:
                    self.token = response.headers["vchs-authorization"]
                    self.instances = self.get_instances()
                    return True
                else:
                    return False
        elif self.service_type == 'vcd':
            if token:
                url = self.host + '/api/sessions'
                vcloud_session = VCS(url, self.username, org, None, org_url, org_url, version=self.version, verify=self.verify)
                result = vcloud_session.login(token=token)
                if result:
                    self.org = org
                    self.vcloud_session = vcloud_session
                return result
            else:
                url = self.host + '/api/sessions'
                vcloud_session = VCS(url, self.username, org, None, org_url, org_url, version=self.version, verify=self.verify)
                result = vcloud_session.login(password=password)
                if result:
                    self.token = vcloud_session.token
                    self.org = org
                    self.vcloud_session = vcloud_session
                return result
        else:
            return False
        return False
        
    #ondemand
    def get_plans(self):
        headers = self._get_vcloud_headers()
        headers['Accept'] = "application/json;version=%s;class=com.vmware.vchs.sc.restapi.model.planlisttype" % self.version
        response = requests.get(self.host + "/api/sc/plans", headers=headers, verify=self.verify)
        if response.history[-1]:
            response = requests.get(response.history[-1].headers['location'], headers=headers, verify=self.verify)                    
        if response.status_code == requests.codes.ok:
            return json.loads(response.content)['plans']
        else:
            return None
            
    def get_instances(self):
        response = requests.get(self.host + "/api/sc/instances", headers=self._get_vcloud_headers(), verify=self.verify)
        if response.history[-1]:
            response = requests.get(response.history[-1].headers['location'], headers=self._get_vcloud_headers(), verify=self.verify)                    
        if response.status_code == requests.codes.ok:
            return json.loads(response.content)['instances']
        else:
            return None
            
    def delete_instance(self, instance):
        response = requests.delete(self.host + "/api/sc/instances/" + instance, headers=self._get_vcloud_headers(), verify=self.verify)
        print response.status_code, response.content
    
    def login_to_instance(self, instance, password, token, org_url):
        instances = filter(lambda i: i['id']==instance, self.instances)
        if len(instances)>0:
            attributes = json.loads(instances[0]['instanceAttributes'])
            session_uri = attributes['sessionUri']
            org_name = attributes['orgName']
            vcloud_session = VCS(session_uri, self.username, org_name, instance, instances[0]['apiUrl'], org_url, version=self.version, verify=self.verify)
            result = vcloud_session.login(password, token)
            if result:
                self.vcloud_session = vcloud_session
                return True
        return False
    
    #subscription
    def get_vdc_references(self, serviceId):
        serviceReferences = filter(lambda serviceReference: serviceReference.get_serviceId() == serviceId, self.services.get_Service())
        if len(serviceReferences) == 0:
            return []
        response = requests.get(serviceReferences[0].get_href(), headers=self._get_vcloud_headers(), verify=self.verify)
        vdcs = vchsType.parseString(response.content, True)
        return vdcs.get_VdcRef()        
        
    def get_vdc_reference(self, serviceId, vdcId):
        vdcReferences = filter(lambda vdcRef: vdcRef.get_name() == vdcId, self.get_vdc_references(serviceId))
        if len(vdcReferences) == 0:
            return None
        return vdcReferences[0]
            
    def login_to_vdc(self, service, vdc):
        vdcReference = self.get_vdc_reference(service, vdc)
        if vdcReference:
            link = filter(lambda link: link.get_type() == "application/xml;class=vnd.vmware.vchs.vcloudsession", vdcReference.get_Link())[0]
            response = requests.post(link.get_href(), headers=self._get_vcloud_headers(), verify=self.verify)
            if response.status_code == requests.codes.created:
                vchs = vchsType.parseString(response.content, True)
                vdcLink = vchs.get_VdcLink()
                headers = {}
                headers[vdcLink.authorizationHeader] = vdcLink.authorizationToken
                headers["Accept"] = "application/*+xml;version=" + self.version
                response = requests.get(vdcLink.href, headers=headers, verify=self.verify)
                if response.status_code == requests.codes.ok:                    
                    self.vdc = vdcType.parseString(response.content, True)
                    self.org = self.vdc.name                    
                    org_url = filter(lambda link: link.get_type() == "application/vnd.vmware.vcloud.org+xml", self.vdc.get_Link())[0].href
                    vcloud_session = VCS(org_url, self.username, self.org, None, org_url, org_url, version=self.version, verify=self.verify)
                    if vcloud_session.login(password=None, token=vdcLink.authorizationToken):
                        self.vcloud_session = vcloud_session
                        return True
        return False
        
    #common
    def _get_vcloud_headers(self):
        headers = {}        
        if self.service_type == 'subscription':
            headers["Accept"] = "application/xml;version=" + self.version            
            headers["x-vchs-authorization"] = self.token
        elif self.service_type == 'ondemand':
            headers["Authorization"] = "Bearer %s" % self.token
            headers["Accept"] = "application/json;version=%s" % self.version
        elif self.service_type == 'vcd':
            # headers["x-vcloud-authorization"] = self.token
            pass
        return headers 

    def get_vdc_templates(self):
        pass
        
    def get_vdc(self, vdc_name):
        if self.vcloud_session and self.vcloud_session.organization:
            refs = filter(lambda ref: ref.name == vdc_name and ref.type_ == 'application/vnd.vmware.vcloud.vdc+xml', self.vcloud_session.organization.Link)
            if len(refs) == 1:
                response = requests.get(refs[0].href, headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                if response.status_code == requests.codes.ok:
                    # print response.content
                    return vdcType.parseString(response.content, True)
                    
    def get_vapp(self, vdc, vapp_name):
        refs = filter(lambda ref: ref.name == vapp_name and ref.type_ == 'application/vnd.vmware.vcloud.vApp+xml', vdc.ResourceEntities.ResourceEntity)
        if len(refs) == 1:
            response = requests.get(refs[0].href, headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
            if response.status_code == requests.codes.ok:
                vapp = VAPP(vAppType.parseString(response.content, True), self.vcloud_session.get_vcloud_headers(), self.verify)
                return vapp
                
    def create_vapp(self, vdc_name, vapp_name, template_name, catalog_name, network_name=None, network_mode='bridged'):
        self.vdc = self.get_vdc(vdc_name)
        if not self.vcloud_session or not self.vcloud_session.organization or not self.vdc:        
            #"Select an organization and datacenter first"
            return False
        catalogs = filter(lambda link: catalog_name == link.get_name() and link.get_type() == "application/vnd.vmware.vcloud.catalog+xml", self.vcloud_session.organization.get_Link())
        if len(catalogs) == 1:
            response = requests.get(catalogs[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
            if response.status_code == requests.codes.ok:
                catalog = catalogType.parseString(response.content, True)
                catalog_items = filter(lambda catalogItemRef: catalogItemRef.get_name() == template_name, catalog.get_CatalogItems().get_CatalogItem())
                if len(catalog_items) == 1:
                    response = requests.get(catalog_items[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                    # use ElementTree instead because none of the types inside resources (not even catalogItemType) is able to parse the response correctly
                    catalogItem = ET.fromstring(response.content)
                    entity = [child for child in catalogItem if child.get("type") == "application/vnd.vmware.vcloud.vAppTemplate+xml"][0]
                    template_params = VAPP.create_instantiateVAppTemplateParams(vapp_name, entity.get("href"))
                    # import sys; template_params.export(sys.stdout, 0)
                    if network_name:
                        pass
                    output = StringIO()
                    template_params.export(output, 
                        0,
                        name_ = 'InstantiateVAppTemplateParams',
                        namespacedef_ = 'xmlns="http://www.vmware.com/vcloud/v1.5" xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1"',
                        pretty_print = False)
                    body = '<?xml version="1.0" encoding="UTF-8"?>' + \
                            output.getvalue().replace("ovf:Section", "NetworkConfigSection", 2).replace('Info msgid=""', "ovf:Info").replace("/Info", "/ovf:Info")
                    
                    content_type = "application/vnd.vmware.vcloud.instantiateVAppTemplateParams+xml"

                    link = filter(lambda link: link.get_type() == content_type, self.vdc.get_Link())
                    response = requests.post(link[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify, data=body)
                    if response.status_code == requests.codes.created:
                        vApp = vAppType.parseString(response.content, True)
                        task = vApp.get_Tasks().get_Task()[0]
                        return task
                    else:
                        return False
                else:
                    return False
            else:
                return False
        else:
            return False
            
    def block_until_completed(self, task):
        progress = task.get_Progress()
        status = task.get_status()
        rnd = 0
        while status != "success":
            if status == "error":
                error = task.get_Error()
                return False
            else:
                # some task doesn't not report progress
                if progress:
                    pass
                else:
                    rnd += 1
                time.sleep(1)
                response = requests.get(task.get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                if response.status_code == requests.codes.ok:                    
                    task = taskType.parseString(response.content, True)
                    progress = task.get_Progress()
                    status = task.get_status()
                else:
                    return False
        return True
                    
    def delete_vapp(self, vdc_name, vapp_name):
        self.vdc = self.get_vdc(vdc_name)
        if not self.vcloud_session or not self.vcloud_session.organization or not self.vdc: return False        
        vapp = self.get_vapp(self.vdc, vapp_name)
        if not vapp: return False
        #undeploy and remove
        if vapp.me.deployed:
            task = vapp.undeploy()
            if task: 
                self.block_until_completed(task)
            else:
                return False
        vapp = self.get_vapp(self.vdc, vapp_name)
        if vapp: return vapp.delete()
                                
    def create_catalog(self, catalog_name, description):
        refs = filter(lambda ref: ref.rel == 'add' and ref.type_ == 'application/vnd.vmware.admin.catalog+xml', self.vcloud_session.organization.Link)
        if len(refs) == 1:
            data = """<?xml version="1.0" encoding="UTF-8"?>
            <AdminCatalog xmlns="http://www.vmware.com/vcloud/v1.5" name="%s">
            <Description>%s</Description>
            </AdminCatalog>            
            """ % (catalog_name, description)
            response = requests.post(refs[0].href, headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify, data=data)
            if response.status_code == requests.codes.created:
                task = vCloudEntities.parseString(response.content, True)
                return task.get_Tasks().get_Task()[0]
                
    #todo, get the url from the server, this doesn't work in ondemand
    def delete_catalog(self, catalog_name):
        return False
        # refs = filter(lambda ref: ref.name == catalog_name and ref.type_ == 'application/vnd.vmware.vcloud.catalog+xml', self.vcloud_session.organization.Link)
        # if len(refs) == 1:
        #     id = refs[0].href.split("/")[-1]
        #     from urlparse import urlparse
        #     o = urlparse(refs[0].href)
        #     href = o.scheme + "://" + o.netloc + "/api/compute/api/admin/catalog/" + id
        #     response = requests.delete(href, headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
        #     if response.status_code == requests.codes.no_content:
        #         return True
        #     else:
        #         return False
        # return False
        
    def get_gateways(self, vdc_name):
        gateways = []
        link = filter(lambda link: link.get_rel() == "edgeGateways", self.get_vdc(vdc_name).get_Link())
        response = requests.get(link[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
        if response.status_code == requests.codes.ok:            
            queryResultRecords = queryRecordViewType.parseString(response.content, True)
            if queryResultRecords.get_Record():
                for edgeGatewayRecord in queryResultRecords.get_Record():
                    response = requests.get(edgeGatewayRecord.get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                    if response.status_code == requests.codes.ok:
                        gateway = Gateway(networkType.parseString(response.content, True), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                        gateways.append(gateway)
        return gateways
        
    def get_gateway(self, vdc_name, gateway_name):
        gateway = None
        link = filter(lambda link: link.get_rel() == "edgeGateways", self.get_vdc(vdc_name).get_Link())
        response = requests.get(link[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
        if response.status_code == requests.codes.ok:            
            queryResultRecords = queryRecordViewType.parseString(response.content, True)
            if queryResultRecords.get_Record():
                for edgeGatewayRecord in queryResultRecords.get_Record():
                    if queryResultRecord.get_Name() == gateway_name:
                        response = requests.get(edgeGatewayRecord.get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                        if response.status_code == requests.codes.ok:
                            gateway = Gateway(networkType.parseString(response.content, True), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                            break
        return gateway        
        
        
    def get_networks(self, vdc_name):
        result = []
        networks = self.get_vdc(vdc_name).get_AvailableNetworks().get_Network()
        for n in networks:
            response = requests.get(n.get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
            if response.status_code == requests.codes.ok:
                network = networkType.parseString(response.content, True)
                result.append(network)
        return result
        
    def parsexml_(self, string_to_parse):
        import xml.etree.ElementTree as ET
        doc = ET.fromstring(string_to_parse)
        return doc
        
    def get_media(self, catalog_name, media_name):
        refs = filter(lambda ref: ref.name == catalog_name and ref.type_ == 'application/vnd.vmware.vcloud.catalog+xml', self.vcloud_session.organization.Link)
        if len(refs) == 1:
            response = requests.get(refs[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
            if response.status_code == requests.codes.ok:
                catalog = catalogType.parseString(response.content, True)
                catalog_items = filter(lambda catalogItemRef: catalogItemRef.get_name() == media_name, catalog.get_CatalogItems().get_CatalogItem())
                if len(catalog_items) == 1:
                    response = requests.get(catalog_items[0].get_href(), headers=self.vcloud_session.get_vcloud_headers(), verify=self.verify)
                    # print response.content
                    if response.status_code == requests.codes.ok:
                        doc = self.parsexml_(response.content)
                        for element in doc._children:
                            if element.tag == '{http://www.vmware.com/vcloud/v1.5}Entity':
                                return element.attrib
                    
    #todo: send DELETE
    def logout(self):
        """
        Request to logout from  vCloud Air.
        
        :return:
        """        
        if self.service_type == 'subscription':
            pass
        elif self.service_type == 'ondemand':
            pass
        elif self.service_type == 'vcd':
            pass
        self.token = None
        self.vcloud_session = None
