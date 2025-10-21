# Robot Web UI (Integrated)

Ova mapa sadrži integrirani web UI (React + Vite) za vizualizaciju i upravljanje robotom.

## Build Docker image
```
docker build -t robot-web-ui:local .
```

## Pokretanje lokalno (dev server)
```
npm ci
npm run dev
```

## Environment varijable
Koristi `VITE_ROSBRIDGE_URL` (npr. `ws://localhost:9090` ili `ws://tailscale-ip:9090`). Ako nije definirano, fallback je host:9090.

## Produkcija kroz stack
Compose servis u `stack/docker-compose.yaml` mapira port 8080:80.

## Napomena
`LICENSE` iz originalnog projekta nije kopiran prema zahtjevu.

three.js tipovi koriste službene `@types/three`; privremeni shim uklonjen.
