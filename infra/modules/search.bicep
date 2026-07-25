param location string
param searchServiceName string = 'search-clinical-rag'

resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'free'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    disableLocalAuth: false
    semanticSearch: 'free'
    networkRuleSet: {
      bypass: 'None'
    }
  }
}

output endpoint string = 'https://${searchService.name}.search.windows.net'
output name string = searchService.name
