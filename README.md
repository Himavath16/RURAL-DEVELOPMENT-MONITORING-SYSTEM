# Rural Development Monitoring System (RDMS)

A role-based web application for transparent reporting and monitoring of rural infrastructure and development projects.

## Portals and capabilities

- **Village Representative Portal**
  - Login with role-restricted access.
  - Submit issues with village name, location, department, problem description, and before-work photo URL.
  - Track complaint status and progress updates.

- **District Authority Portal**
  - View all district issues.
  - Verify and assign issues to officers/departments.
  - Set expected completion timeline.
  - Record construction metadata: contractor, sanctioned budget, material/other costs, workers and vendors.
  - Publish periodic progress updates with optional photo URL and status changes (Pending/In Progress/Completed).

- **State Authority Portal**
  - Monitor all districts through an aggregated dashboard.
  - View district performance and timelines.
  - Audit project progress and completion.

- **Notifications**
  - District receives alert when new village issue is submitted.
  - District + State receive alerts on progress updates and assignment milestones.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

### Demo credentials

All passwords are `password123`:
- Village Representative: `village_rep_1`
- District Authority: `district_admin_a`
- State Authority: `state_admin`

## Notes

- This demo stores data in `rdms.db` (SQLite) and uses plain-text demo passwords for simplicity.
- For production: add password hashing, file uploads, role management, audit logs, API auth, and stronger validation.
