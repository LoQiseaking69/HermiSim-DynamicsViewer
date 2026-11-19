# Code-signing the Windows release

.RAV IDE releases are signed with **Microsoft Artifact Signing** (formerly Trusted Signing). It's
Microsoft's managed code-signing service: the private key lives in Microsoft's HSMs, a short-lived
certificate is issued for each signing, and every signature is timestamped, so signed releases stay
valid after the certificate expires.

The `windows-installer` workflow signs four things:
- `RAVIDE.exe`
- `ravide-cli.exe`
- `tulpa.exe`
- the setup executable and its embedded uninstaller

Once the six secrets below exist, signing switches on automatically. Until then, releases are
published unsigned.

## 1. Eligibility and cost

- **Public Trust identity validation:**
  - Individual developers: USA and Canada.
  - Organizations: USA, Canada, EU and UK. Organizations generally need about 3 years of
    verifiable history.
  - Validate as an **individual**: it needs a government ID plus Microsoft Authenticator (Entra
    Verified ID). The certificate's publisher name becomes your legal name. An organization
    identity only makes sense once HermiTech LLC qualifies.
- **Basic plan:** US$9.99/month for 5,000 signatures. A release uses 5 signatures.
- **Billing:** starts when the Artifact Signing *account* is created.

## 2. Azure setup (one-time, about 30 minutes plus validation time)

1. **Subscription:** at <https://portal.azure.com>, create a subscription if you don't have one.
   Then go to *Subscriptions ▸ Resource providers*, register `Microsoft.CodeSigning`.
2. **Artifact Signing account:** *Create a resource ▸ Artifact Signing account*. Pick a region,
   for example **East US** (endpoint `https://eus.codesigning.azure.net`), and the **Basic** SKU.
3. **Identity validation:** open the account, go to *Objects ▸ Identity validations ▸ New ▸
   Public ▸ Individual*, and complete the Verified ID flow in Microsoft Authenticator. Approval
   usually takes from minutes to a few business days.
4. **Certificate profile:** *Objects ▸ Certificate profiles ▸ Create ▸ Public Trust*. Select the
   validated identity and name the profile, for example `hermisim`.
5. **App registration for GitHub:**
   1. Under *Microsoft Entra ID ▸ App registrations ▸ New registration*, create `hermisim-github-signing`.
   2. Copy its **Application (client) ID** and **Directory (tenant) ID**.
   3. Add the federated credential: *Certificates & secrets ▸ Federated credentials ▸ Add ▸
      GitHub Actions deploying Azure resources*. Use these values:
      - Organization `LoQiseaking69`
      - Repository `HermiSim-DynamicsViewer`
      - Entity **Tag**, pattern `v*` (tag builds)
   4. Add a second federated credential with Entity **Branch** `main`. Manual workflow runs need it.
6. **Role assignment:** on the Artifact Signing account, go to *Access control (IAM) ▸ Add role
   assignment ▸ Artifact Signing Certificate Profile Signer* (named *Trusted Signing Certificate
   Profile Signer* in older portals), and assign it to `hermisim-github-signing`.

No client secret is created, because GitHub logs in with OIDC.

## 3. GitHub secrets

Add these under *Repository ▸ Settings ▸ Secrets and variables ▸ Actions ▸ New repository secret*:

| Secret | Value |
|---|---|
| `AZURE_CLIENT_ID` | the app registration's Application (client) ID |
| `AZURE_TENANT_ID` | the Directory (tenant) ID |
| `AZURE_SUBSCRIPTION_ID` | the subscription holding the signing account |
| `ARTIFACT_SIGNING_ENDPOINT` | e.g. `https://eus.codesigning.azure.net` (must match the account's region) |
| `ARTIFACT_SIGNING_ACCOUNT` | the Artifact Signing account name |
| `ARTIFACT_SIGNING_PROFILE` | the certificate profile name |

## 4. Release

```bash
git tag v2.3.0 && git push origin v2.3.0
```

Alternatively, go to *Actions ▸ windows-installer ▸ Run workflow*, set the version and tick
*publish*. The workflow then:
1. builds the installer
2. signs it
3. verifies the signatures
4. creates the `v<version>` tag and the **.RAV IDE <version>** release, with the installer and its
   SHA-256 attached

The install page is <https://github.com/LoQiseaking69/HermiSim-DynamicsViewer/releases/latest>.

## Signing locally

Run `az login` first, then:

```powershell
$env:ARTIFACT_SIGNING_ENDPOINT="https://eus.codesigning.azure.net"
$env:ARTIFACT_SIGNING_ACCOUNT="<account>"; $env:ARTIFACT_SIGNING_PROFILE="hermisim"
powershell -File installer\windows\build.ps1 -Sign
```

## SmartScreen

A signed installer shows **.RAV IDE / your name** as the publisher instead of "Unknown publisher".
The *Windows protected your PC* screen can still appear for the first few weeks: SmartScreen
reputation builds up per certificate identity as people download and run the installer. Since
2024, no certificate type, EV included, skips that warm-up.

## Alternatives

- **SignPath Foundation:** free for open-source projects. The certificate is issued to SignPath
  Foundation, so it is shown as the publisher. It needs an OSI license and public source for
  everything that gets signed. .RAV IDE bundles `tulpa.exe` built from the **private** TulpaLang
  repo, so the project only qualifies if TulpaLang is made public.
- **Commercial OV certificate with cloud key storage**, such as SSL.com eSigner, DigiCert KeyLocker
  or Sectigo. It costs roughly $200–400 a year and works from any country. To use one, replace the
  `signtool` call in `sign.ps1` with the vendor's CLI.
