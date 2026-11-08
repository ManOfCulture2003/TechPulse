# Security and privacy

This is a local, single-user app. Use the supplied loopback launcher. Do not expose it through a public server, tunnel, reverse proxy, or LAN binding.

The local app requires a random access key from the startup terminal. Keep it private: anyone with that key can access the workspace. Browser sessions use HttpOnly, SameSite=Strict cookies, expire after eight hours, and are revoked on logout or server restart. Five wrong keys cause a 30-second cooldown. There are no customer accounts or per-record tenant permissions.

Default storage is under the current OS user's data directory. Unix app directories use mode 0700; Windows relies on the user profile's inherited ACLs. Custom paths rely on your chosen folder's permissions. The database is not encrypted. This cannot protect against an administrator, malware running as your OS user, another app trusted with the same localhost browser origin, or someone who can read the database/startup terminal. Use separate OS accounts on shared devices.

Private responses are not cached. The app checks Host and browser Origin, blocks framing, limits request bodies, and renders evidence as text. HTTP is only supported on loopback; this is not a secure public-hosting configuration.

The public browser demo is separate. It contains only bundled synthetic data, needs no login, and has no application backend or device collection. Demo notes and exports are local to the visitor's browser. Hosting providers still see ordinary web requests. Never enter sensitive evidence into a public demo.

Keep real logs, database files, access keys and exports out of GitHub. Report problems with a minimal synthetic example. No claim of perfect security, complete detection, or tamper-proof evidence is made.
