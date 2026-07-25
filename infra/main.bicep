targetScope = 'resourceGroup'

param location string = resourceGroup().location
param alertEmail string
param apiImageTag string = 'latest'
param uiImageTag string = 'latest'

module search 'modules/search.bicep' = {
  name: 'search-deploy'
  params: {
    location: location
  }
}

module openai 'modules/openai.bicep' = {
  name: 'openai-deploy'
  params: {
    location: location
  }
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring-deploy'
  params: {
    location: location
    alertEmail: alertEmail
  }
}

module containerapps 'modules/containerapps.bicep' = {
  name: 'containerapps-deploy'
  params: {
    location: location
    logAnalyticsWorkspaceName: monitoring.outputs.logAnalyticsName
    openAiAccountName: openai.outputs.name
    searchServiceName: search.outputs.name
    openAiEndpoint: openai.outputs.endpoint
    searchEndpoint: search.outputs.endpoint
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    apiImageTag: apiImageTag
    uiImageTag: uiImageTag
  }
}

output searchEndpoint string = search.outputs.endpoint
output openAiEndpoint string = openai.outputs.endpoint
output acrLoginServer string = containerapps.outputs.acrLoginServer
output apiUrl string = 'https://${containerapps.outputs.apiFqdn}'
output uiUrl string = 'https://${containerapps.outputs.uiFqdn}'
