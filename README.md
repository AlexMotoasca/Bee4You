# Bee4You

Bee4You is a planned mobile field notebook for beekeepers who manage colonies at permanent apiaries or move them between sites during the season. The aim is to let a beekeeper select a colony, log work at the hive, and put the phone away even when there is no signal.

**Project status:** Planning. The features, architecture, folder layout, and setup steps below describe the intended implementation.

## A visit to the apiary

1. **Find the site.** Select an apiary pin on the interactive Google map or open a previously saved site from the apiary list.
2. **Choose a colony.** Open its history. A stationary colony can stay at one site throughout the season. For a migratory colony, record the move date, origin, and destination so earlier visits remain linked to the site where they took place.
3. **Make a quick entry.** From the colony screen, start a treatment with the colony and apiary already selected. Record the product, date, and amount used. From the apiary screen, log a harvest with its quantity and unit, or adjust inventory when supplies arrive or equipment moves.
4. **Save in the field.** See confirmation once the phone has stored the entry. A separate sync status shows whether the server has received it.

## Architecture and technology stack

```text
Mobile app (Android / iOS)                     Optional web dashboard
React Native + Expo                            Next.js
        |                                          |
        +-- SQLite (field records and sync queue)   |
        |                                          |
        +----------- HTTPS / JSON REST API --------+
                                |
                         Java / Spring Boot
                                |
                            PostgreSQL
```

### Mobile frontend

| Technology | Role |
| --- | --- |
| React Native, TypeScript, Expo | Build the Android and iOS field app from a shared codebase. |
| Expo Router | Navigate between the map, apiary, colony history, and entry screens. |
| NativeWind | Style forms, lists, map controls, and sync indicators consistently. |
| react-native-maps | Display apiary markers with Google Maps as the provider on both platforms. |
| expo-sqlite | Store the beekeeper’s downloaded records and pending changes on the device across app restarts. [Expo SQLite documentation](https://docs.expo.dev/versions/latest/sdk/sqlite/) |

### Backend

| Technology | Role |
| --- | --- |
| Java, Spring Boot | Expose the REST API and validate field entries and sync requests. |
| PostgreSQL | Hold the central records shared across a beekeeper’s devices. |
| Spring Data JPA, Hibernate | Map Java entities to database tables and handle persistence. |
| Spring Security, JWT | Authenticate API requests and check the user’s access to each apiary. |
| Flyway | Version and apply PostgreSQL schema migrations. |
| OpenAPI | Document request bodies, responses, and errors for both clients. |

The optional **Next.js dashboard** would use the same authenticated API to review colony histories, harvest totals, and inventory on a larger screen. The mobile workflow can ship independently.

## Offline saves and sync

On the first connected sign-in, the app would download the beekeeper’s selected apiaries and colonies. Subsequent visits could use those local records. The proposed sync flow is:

1. Save the field entry and its pending change in one SQLite transaction. Assign a stable identifier before upload.
2. When the app is active and the API is reachable, send queued changes. The API should recognize retried changes so a dropped connection cannot count the same harvest twice.
3. Mark each accepted change as synced and pull newer server records. If two devices edit the same record, retain the local edit and flag the conflict for review.

**Field limits.** A new device needs a connection for sign-in and its first download. Unsynced entries exist only on the device and can be lost if app data is cleared. An expired session may require sign-in before uploads resume.

**Map limits.** SQLite holds saved apiary names and coordinates. Basemap imagery at a particular location or zoom level may be unavailable offline. The planned fallback is a searchable list of saved apiaries with access to their colonies and quick-entry forms. Downloadable offline map regions are outside the planned scope.

## Feature roadmap

| Phase | Planned milestone | Completion check |
| --- | --- | --- |
| 1 · Apiaries and colonies | Sign-in, map and list views, colony profiles, stationary placements, and dated moves | Move a colony between sites and find both placements in its history. |
| 2 · Field records | Treatment logs, harvest quantities, inventory adjustments, and contextual quick entry | Record a treatment from a colony screen without reselecting the colony. |
| 3 · Offline field testing | Local saves, queued sync, retry handling, and conflict review | Log a harvest in airplane mode, restart the app, reconnect, and verify one server entry. |
| 4 · Optional dashboard | Next.js views for records and summaries | Review a synced mobile harvest from a browser. |

## Proposed project structure

```text
bee4you/
├── apps/
│   ├── mobile/
│   │   └── src/
│   │       ├── app/          # Expo Router screens and layouts
│   │       ├── features/     # Apiaries, colonies, treatments, harvests, inventory
│   │       ├── db/           # Device schema and SQLite migrations
│   │       └── sync/         # Pending changes, retries, conflict handling
│   └── web/                  # Optional Next.js dashboard
├── backend/
│   └── src/main/
│       ├── java/             # API, domain services, persistence, security
│       └── resources/
│           └── db/migration/  # Flyway migrations
└── README.md
```

## Development setup plan

These steps are for scaffolding the project. Choose compatible versions and commit the package lockfile and Java build wrapper when the first projects are created.

1. **Prepare the tools.** Install Node.js LTS and npm, a JDK supported by the selected Spring Boot release, and PostgreSQL. Have an Android or iOS device available for field testing. Local native builds require Android Studio for Android or macOS with Xcode for iOS.
2. **Create the backend.** Generate a Spring Boot project with web, security, JWT resource server support, JPA, PostgreSQL, and Flyway dependencies. Add OpenAPI support compatible with the chosen Spring Boot version. Create a development database and user, then configure `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, and `SPRING_DATASOURCE_PASSWORD`. Define an initial Flyway migration before starting the API.
3. **Configure authentication.** Choose a JWT issuer and configure Spring Security to validate its issuer and signature. Define how the mobile client obtains and renews tokens. Keep database credentials and any private signing keys on the server.
4. **Create the mobile project.** Scaffold a TypeScript Expo app with Expo Router. From its directory, install the native dependencies with `npx expo install expo-sqlite react-native-maps`, then configure NativeWind for the selected Expo version. Point the proposed `EXPO_PUBLIC_API_URL` setting at an API address reachable from the test device. On a physical phone, `localhost` refers to the phone itself.
5. **Enable Google Maps.** Configure a Google Cloud project with billing and enable the Maps SDKs for Android and iOS. Restrict each platform key to its SDK and app identity: Android package name and signing certificate fingerprint, or iOS bundle identifier. Configure the keys in the Expo maps plugin, select the Google provider, and rebuild the native app. [Expo Google Maps setup](https://docs.expo.dev/versions/latest/sdk/map-view/)
6. **Verify the first field workflow.** Once the screens and API exist, sign in, download one apiary, and disable connectivity. Save a treatment, close and reopen the app, then reconnect. Check that the treatment stays visible locally and appears exactly once on the server.
