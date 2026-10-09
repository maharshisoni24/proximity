# Location Recommender API

A FastAPI service that finds the 10 closest locations matching a category within a given radius, ranked by actual shortest-path distance over a dynamically provided road network.

## Setup & Run

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 5000
```

*Note: Requires `locations.csv` in the same directory (or set `LOCATIONS_CSV` env var).*

## Usage

**POST** `/search/`

| Field | Type | Description |
|-------|------|-------------|
| `lat` | Form | Current latitude |
| `long` | Form | Current longitude |
| `cat` | Form | Required category (e.g., `bank`) |
| `rad` | Form | Euclidean search radius |
| `link`| File | `.txt` file containing road network edges (e.g., `ID1 ID2` per line) |

**Example:**
```bash
curl -X POST http://localhost:5000/search/ \
  -F "lat=0.5" -F "long=0.5" -F "cat=bank" -F "rad=0.3" \
  -F "link=@link.txt"
```
