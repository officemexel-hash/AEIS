# CODEX PARALLEL INTEGRATION CONTRACTS

**Status:** draft 0.1  
**Cel:** ustalic, co A, B, K i D maja sobie dostarczyc, zeby nie wchodzic jednoczesnie w te same pliki

## 1. Contract A -> B

Agent A dostarcza semantyke i miejsca wpiecia dla:

- unified Human Gate ticket contract
- workspace -> project_mode hook points
- council/model registry truth contract
- worker pool reconciliation lifecycle

Agent B nie zmienia tych kontraktow, tylko dostarcza:

- skills runtime provider
- memory provider
- mobile provider

## 2. Contract A -> K

Agent A dostarcza:

- sposob emitowania unified governance tickets
- event schema dla funding -> Human Gate bridge

Agent K dostarcza:

- funding scanner / reporting / browser actions zgodne z ta semantyka
- observability events i readiness signals

## 3. Contract B -> D

Agent B ma przekazac D:

- jak bootstrappowac skills runtime
- jak bootstrappowac memory startup plane
- jakie nowe mobile routes trzeba zamontowac
- jakie frontend mobile/client bindings trzeba wlaczyc

## 4. Contract K -> D

Agent K ma przekazac D:

- jakie funding routes trzeba domontowac
- jak funding emituje governance events
- jakie observability routes/exporters trzeba wlaczyc
- jakie legacy cleanup flags i runtime scripts trzeba zintegrowac

## 5. Shared proof contract

Kazdy agent ma oddac:

- liste plikow zmienionych w ownership scope
- liste testow uruchomionych
- liste znanych ograniczen
- liste zmian wymagajacych finalnego mountu przez D

## 6. Final contract for D

Agent D nie buduje juz nowych subsystemow.

Agent D:

- montuje istniejace zmiany do wspolnego runtime
- naprawia shared startup lifecycle
- dopina shared router/client/app
- uruchamia scenariusze S1-S8
- robi browser audit
- wydaje finalny verdict
