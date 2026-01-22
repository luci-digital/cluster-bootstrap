{
  "subject": {{ toJson .Subject }},
  "sans": {{ toJson .SANs }},
  {{- if typeIs "*rsa.PublicKey" .Insecure.CR.PublicKey }}
  "keyUsage": ["keyEncipherment", "digitalSignature"],
  {{- else }}
  "keyUsage": ["digitalSignature"],
  {{- end }}
  "extKeyUsage": ["serverAuth", "clientAuth"],
  "extensions": [
    {
      "id": "1.3.6.1.4.1.57264.1.1",
      "critical": false,
      "value": {{ toJson .Token.genesis_bond_id }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.2",
      "critical": false,
      "value": {{ toJson .Token.lineage_did }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.3",
      "critical": false,
      "value": {{ toJson .Token.tier }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.4",
      "critical": false,
      "value": {{ toJson .Token.frequency_hz }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.5",
      "critical": false,
      "value": {{ toJson .Token.coherence_threshold }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.6",
      "critical": false,
      "value": {{ toJson .Token.hedera_topic }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.7",
      "critical": false,
      "value": {{ toJson .Token.agent_name }}
    },
    {
      "id": "1.3.6.1.4.1.57264.1.8",
      "critical": false,
      "value": {{ toJson .Token.ipv6_tid }}
    }
  ]
}
