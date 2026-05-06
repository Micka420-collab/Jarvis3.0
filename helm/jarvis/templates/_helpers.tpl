{{- define "jarvis.name" -}}
{{- default "jarvis" .Chart.Name -}}
{{- end -}}

{{- define "jarvis.labels" -}}
app.kubernetes.io/name: {{ include "jarvis.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "jarvis.image" -}}
{{ .Values.global.imageRegistry }}/jarvis-{{ .name }}:{{ default $.Values.global.imageTag .tag }}
{{- end -}}

{{- define "jarvis.envFrom" -}}
- configMapRef: { name: jarvis-config }
- secretRef:    { name: jarvis-secrets }
{{- end -}}
