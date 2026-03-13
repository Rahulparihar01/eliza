{{/*
Expand the name of the chart.
*/}}
{{- define "eliza.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "eliza.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "eliza.labels" -}}
helm.sh/chart: {{ include "eliza.name" . }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: eliza-adoption
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}

{{/*
Selector labels for a specific component
*/}}
{{- define "eliza.selectorLabels" -}}
app.kubernetes.io/name: {{ include "eliza.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Secret name (either existing or chart-created)
*/}}
{{- define "eliza.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- include "eliza.fullname" . }}-secrets
{{- end }}
{{- end }}

{{/*
ConfigMap name
*/}}
{{- define "eliza.configMapName" -}}
{{- include "eliza.fullname" . }}-config
{{- end }}

{{/*
Database URL construction
*/}}
{{- define "eliza.databaseUrl" -}}
{{- if .Values.postgresql.external.enabled }}
postgresql://{{ .Values.postgresql.external.username }}:$(DB_PASSWORD)@{{ .Values.postgresql.external.host }}:{{ .Values.postgresql.external.port }}/{{ .Values.postgresql.external.database }}
{{- else }}
postgresql://eliza:$(DB_PASSWORD)@{{ include "eliza.fullname" . }}-postgres:5432/ai_enablement
{{- end }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "eliza.redisHost" -}}
{{- if .Values.redis.external.enabled }}
{{- .Values.redis.external.host }}
{{- else }}
{{- include "eliza.fullname" . }}-redis
{{- end }}
{{- end }}

{{/*
Redis port
*/}}
{{- define "eliza.redisPort" -}}
{{- if .Values.redis.external.enabled }}
{{- .Values.redis.external.port }}
{{- else }}
6379
{{- end }}
{{- end }}

{{/*
Backend image reference
*/}}
{{- define "eliza.backendImage" -}}
{{- if .Values.image.registry }}
{{- printf "%s%s:%s" .Values.image.registry .Values.image.backend.repository .Values.image.backend.tag }}
{{- else }}
{{- printf "%s:%s" .Values.image.backend.repository .Values.image.backend.tag }}
{{- end }}
{{- end }}

{{/*
Frontend image reference
*/}}
{{- define "eliza.frontendImage" -}}
{{- if .Values.image.registry }}
{{- printf "%s%s:%s" .Values.image.registry .Values.image.frontend.repository .Values.image.frontend.tag }}
{{- else }}
{{- printf "%s:%s" .Values.image.frontend.repository .Values.image.frontend.tag }}
{{- end }}
{{- end }}
