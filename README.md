# SwiftSend SwiftSend 2.0 — Django Delivery Management System

SwiftSend 2.0 is a substantial upgrade of the original Django delivery project. It keeps the existing `users` and `deliveries` apps and extends the original delivery workflow into a more realistic small-to-medium courier operations platform.

## What is included

### Operations and dispatch
- Operations dashboard with total, pending, active, in-transit, delivered-today and failed-delivery metrics.
- Delivery creation and editing with customer contact details, collection/drop-off addresses, optional coordinates, parcel description and weight, priority, scheduled time, estimated delivery time, driver instructions and internal-only notes.
- Search and filters for delivery reference, tracking token, customer, phone, address, status and priority.
- Driver and vehicle assignment, with a notification and an audit-trail event when a driver is allocated.
- Fleet register for motorcycles, cars, vans and trucks.
- Delivery timeline recording creation, dispatch and driver status changes.
- CSV export and a weekly performance summary by driver.

### Driver workspace
- Drivers see only deliveries assigned to their own account.
- Driver workflow supports Assigned → Picked up → In transit → Delivered, with delivery-failed and return-to-depot exception paths.
- A delivery cannot be completed without recording the recipient's name.
- Drivers can add handover notes and an optional proof-of-delivery image (maximum 5 MB; valid image files only).
- Driver location sharing is opt-in. Drivers can start, resume or stop sharing from their own workspace.

### GPS and customer tracking
- The browser Geolocation API reads the driver's device location only after the driver enables sharing and grants the browser permission.
- Latest positions are stored for the dispatch map. A GPS history point is stored at most every 15 seconds.
- The live fleet map refreshes every 15 seconds.
- Each delivery receives a unique, unguessable customer tracking token. The public tracking page refreshes every 20 seconds.
- Customers see only the current delivery's status, destination, ETA and (when the job is in transit and the driver is actively sharing) the driver's latest position. Customer email, phone, internal notes and the full driver history are not exposed.
- Proof-of-delivery files are served through an authenticated view to operations staff or the driver assigned to that delivery.

## Technology

- Python 3.11+ compatible project layout
- Django 5.2
- SQLite for local development; optional PostgreSQL configuration
- Bootstrap 5, custom responsive CSS, Bootstrap Icons
- Leaflet maps with OpenStreetMap map tiles
- Browser Geolocation API

The original project's Channels/WebSocket placeholder has been removed from the primary delivery flow. The current dashboards use authenticated JSON endpoints and controlled polling. This avoids relying on the original in-memory channel layer, which is not a suitable production message broker.

## Run locally in VS Code (Windows PowerShell)

1. Extract the project ZIP and open the `DMTS_V2` folder in VS Code.
2. Open **Terminal → New Terminal** and run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

If PowerShell blocks virtual-environment activation, run this once in that terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Open:
- Operations login: `http://127.0.0.1:8000/users/login/`
- Django administration: `http://127.0.0.1:8000/admin/`

The superuser created by `createsuperuser` can enter the operations workspace. The account role defaults to **Operations staff**.

## Create staff and driver accounts

1. Sign in to `/admin/` using the superuser credentials.
2. Open **Users → Users → Add user**.
3. Select **Driver** for driver accounts. Select **Operations staff**, **Dispatcher** or **Customer support** for staff-side accounts.
4. Enter the user's name, email and phone number, then save.
5. Add vehicles from **Fleet & vehicles** in the operations interface.
6. Create a delivery and use **Dispatch** to allocate a driver and vehicle.

Django admin is the account administration interface in this version. Do not share the superuser login with drivers.

## Enable real GPS tracking

Live GPS requires all of the following:

1. Open the driver workspace on a GPS-capable phone or tablet.
2. Use **HTTPS** in a deployed environment. Browser geolocation is generally blocked on an ordinary HTTP network address; `localhost` is allowed for local development on the same device.
3. Turn on the phone's location services and grant the browser permission when prompted.
4. Tap **Start sharing**. The browser then sends GPS coordinates to the server while the page is open and the browser allows it to run.
5. Open **Live fleet map** as operations staff. The driver appears once a fresh GPS position has arrived.
6. Share the unique customer tracking link from a delivery record. The customer's map shows the driver only while that delivery is **In transit**, location sharing is enabled and the last GPS update is recent.

**Important real-world limitation:** a mobile browser may pause geolocation when the phone locks, the tab is backgrounded, the browser is closed or the operating system conserves battery. This implementation provides real device GPS while the browser is actively permitted to run; it is not a native background-tracking app. For dependable all-day background tracking, build a dedicated Android/iOS driver app or managed device agent.

The map uses OpenStreetMap tiles and Leaflet from public CDN services. A commercial deployment with significant traffic should choose a tile provider and hosting plan appropriate to its expected usage and service requirements.

## Preserve the data from your original DMTS project

The new ZIP intentionally does **not** include your old `db.sqlite3` file, so it does not redistribute your existing account records or database contents.

To upgrade the original database:

1. Make a backup of the original `db.sqlite3` file.
2. Copy that database into the root of the `DMTS_V2` folder (next to `manage.py`).
3. Install the new requirements and run:

```powershell
python manage.py migrate
```

Migration `deliveries.0003` adds the new fields and generates a unique tracking token for every existing delivery. Your original delivery records and user accounts are retained. The upgrade migration was tested against the database included in the uploaded project: all 6 existing delivery records migrated successfully and received tracking codes.

For a fresh install, simply run `python manage.py migrate` without copying the previous database.

## Configuration and deployment notes

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` and database environment variables should be set in the hosting provider. Never deploy with the development secret key or `DJANGO_DEBUG=1`.
- SQLite is the default for local development. For a multi-user production deployment, use PostgreSQL by setting `DB_ENGINE=postgresql` and the `DB_*` variables in `.env.example`.
- Set `DJANGO_DEBUG=0`, configure HTTPS, allowed hosts and trusted origins, then run `python manage.py collectstatic`.
- Use a production server such as Gunicorn behind a properly configured reverse proxy. Serve static assets through the proxy/CDN. Keep uploaded proof-of-delivery media private; do **not** expose the whole `MEDIA_ROOT` directory as a public static folder.
- The default email backend prints email to the development console. There is no SMS, WhatsApp or production email gateway configured.
- Schedule `python manage.py purge_location_history --days 30` regularly (for example, daily or weekly) to remove older GPS history points. Set a retention period that matches the company's documented privacy and operational policy.
- Review applicable privacy, employment, customer-notification, security, backup and data-retention requirements before using this with a real delivery company. This project is a strong working foundation, not a completed compliance or security certification.

## Known scope boundaries

This is an operational Version 2 foundation, not a full enterprise TMS. It currently does not provide automatic address geocoding, traffic-aware route optimisation, proof-of-delivery signature capture, real SMS/WhatsApp/email notifications, payment collection, accounting integration, or guaranteed background GPS. The route coordinates can be entered on the delivery form; live driver coordinates come from the driver's device.

## Tests and checks

Run:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test deliveries
```

The included suite currently contains 10 automated tests. They cover staff/driver access separation, driver delivery scoping, GPS opt-in and coordinate updates, customer tracking visibility, dispatch notifications, delivery creation/audit events and key page rendering.
