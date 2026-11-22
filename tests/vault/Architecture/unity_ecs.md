---
id: unity_ecs
title: Архітектура конвеєра променевого трасування в Unity
tags: [jarlight, ecs]
---
# Архітектура конвеєра променевого трасування в Unity

## Підсистема Raycast-трасування світла
Системи ISystem компілюються через BurstCompile без GameObject.Find та алокацій у OnUpdate.
