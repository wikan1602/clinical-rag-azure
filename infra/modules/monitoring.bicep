param location string
param alertEmail string
param logAnalyticsName string = 'law-clinical-rag'
param appInsightsName string = 'appinsights-clinical-rag'
param actionGroupName string = 'ag-clinical-rag'
// Matches the existing live workbook's resource name so this redeploy updates
// it in place instead of creating a duplicate workbook alongside it.
param workbookResourceName string = '1615665b-f02b-4ddf-9200-2fd67c51b92b'

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 90
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
    IngestionMode: 'LogAnalytics'
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: actionGroupName
  location: 'global'
  properties: {
    groupShortName: 'clinicrag'
    enabled: true
    emailReceivers: [
      {
        name: 'wikan-email'
        emailAddress: alertEmail
        useCommonAlertSchema: false
      }
    ]
  }
}

resource highLatencyAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-high-latency'
  location: 'global'
  properties: {
    severity: 2
    enabled: true
    scopes: [
      appInsights.id
    ]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'cond0'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: 5000
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

resource lowFaithfulnessAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-low-faithfulness'
  location: location
  properties: {
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [
      appInsights.id
    ]
    criteria: {
      allOf: [
        {
          query: 'traces | where message == \'eval_summary\' | extend faithfulness = todouble(customDimensions.faithfulness) | where faithfulness < 0.85'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
    autoMitigate: true
    checkWorkspaceAlertsStorageConfigured: false
    skipQueryValidation: false
  }
}

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: workbookResourceName
  location: location
  kind: 'shared'
  properties: {
    displayName: 'Clinical RAG Monitoring'
    category: 'workbook'
    sourceId: appInsights.id
    serializedData: string({
      version: 'Notebook/1.0'
      items: [
        {
          type: 1
          content: {
            json: '# Clinical Knowledge Assistant — Monitoring Dashboard'
          }
          name: 'text - title'
        }
        {
          type: 3
          content: {
            version: 'KqlItem/1.0'
            query: 'requests\n| summarize avg(duration) by bin(timestamp, 1h)\n| order by timestamp asc'
            size: 0
            title: 'Latency Trend (avg request duration, ms)'
            timeContext: {
              durationMs: 604800000
            }
            queryType: 0
            resourceType: 'microsoft.insights/components'
            visualization: 'timechart'
          }
          name: 'query - latency'
        }
        {
          type: 3
          content: {
            version: 'KqlItem/1.0'
            query: 'traces\n| where message == "generation_answer"\n| extend prompt_tokens = toint(customDimensions.prompt_tokens), completion_tokens = toint(customDimensions.completion_tokens)\n| summarize sum(prompt_tokens), sum(completion_tokens) by bin(timestamp, 1h)\n| order by timestamp asc'
            size: 0
            title: 'Token Usage Trend (cost proxy)'
            timeContext: {
              durationMs: 604800000
            }
            queryType: 0
            resourceType: 'microsoft.insights/components'
            visualization: 'timechart'
          }
          name: 'query - cost'
        }
        {
          type: 3
          content: {
            version: 'KqlItem/1.0'
            query: 'traces\n| where message == "eval_summary"\n| extend strategy = tostring(customDimensions.strategy), faithfulness = todouble(customDimensions.faithfulness), answer_relevancy = todouble(customDimensions.answer_relevancy), context_precision = todouble(customDimensions.context_precision), context_recall = todouble(customDimensions.context_recall)\n| project timestamp, strategy, faithfulness, answer_relevancy, context_precision, context_recall\n| order by timestamp asc'
            size: 0
            title: 'Eval Score Trend (per run)'
            timeContext: {
              durationMs: 2592000000
            }
            queryType: 0
            resourceType: 'microsoft.insights/components'
            visualization: 'table'
          }
          name: 'query - eval'
        }
      ]
      isLocked: false
      fallbackResourceIds: [
        appInsights.id
      ]
    })
  }
}

output appInsightsConnectionString string = appInsights.properties.ConnectionString
output appInsightsId string = appInsights.id
output logAnalyticsId string = logAnalytics.id
output logAnalyticsName string = logAnalytics.name
