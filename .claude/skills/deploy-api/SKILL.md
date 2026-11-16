---
name: deploy-api
description: Deploy API to cloud provider
parameters:
  hosting:
    type: enum
    values: [vercel, aws, gcp, azure, railway]
    required: true
    infer_from: '\b(vercel|aws|gcp|azure|railway)\b'
  framework:
    type: enum
    values: [fastapi, express, django, rails, hono]
    infer_from: '\b(fastapi|express|django|rails|hono)\b'
  replicas:
    type: int
    default: 1
    min: 1
    max: 10
---

# Deploy API

Deploy your API application to a cloud hosting provider.

## When to Use

Use this skill when you want to:
- Deploy a FastAPI/Express/Django/Rails app to the cloud
- Configure hosting on Vercel, AWS, GCP, Azure, or Railway
- Set up production deployment configuration

## Typed Parameters

This skill uses typed parameters with automatic extraction:

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `hosting` | enum | Yes | - | Cloud provider (vercel, aws, gcp, azure, railway) |
| `framework` | enum | No | - | Backend framework (fastapi, express, django, rails, hono) |
| `replicas` | int | No | 1 | Number of replicas (1-10) |

## How It Works

1. Parameters are extracted from your prompt using regex patterns
2. Missing required parameters trigger clarification questions
3. Default values are used for optional parameters not specified

## Example Prompts

**Full specification:**
```
Deploy my FastAPI app to AWS with 3 replicas
```
Result: All parameters extracted, proceeds immediately.

**Partial specification:**
```
Deploy to AWS
```
Result: `hosting` extracted. May ask about `framework` if needed.

**Minimal:**
```
Deploy my app
```
Result: Both `hosting` and `framework` unknown, clarification requested.

## Process

1. Extract parameter values from prompt
2. Check E(X,Q) - if unknown parameters exist, ask user
3. Once all required params known, generate deployment config
4. Create necessary files (Dockerfile, config, etc.)
5. Provide deployment commands
