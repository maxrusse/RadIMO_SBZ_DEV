"""Quick operational readiness helper.

Loads the Flask app, prints a summary of currently configured modalities and skills,
then runs the inline operational checks (config/admin password/uploads directory).
Use this script right after pulling the latest main branch to verify the deployment
is ready for a test system before starting the server.
"""
from pprint import pprint

import app


def main() -> None:
    print("Loaded modalities:")
    pprint(app.APP_CONFIG.get('modalities', {}))
    print("\nConfigured skills (in display order):")
    pprint([entry['label'] for entry in app.SKILL_TEMPLATES])
    print("\nOperational checks:")
    pprint(app.run_operational_checks('cli', force=True))


if __name__ == '__main__':
    main()
