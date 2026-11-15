# Connecting a real payment provider

The module talks to the provider only through `payment_network/providers/base.py` (`PaymentProvider`). The sandbox provider `Mock` is installed; a real one is added without touching anything else.

1. Create `payment_network/providers/<name>.py` with a class that implements the four methods:
   - `charge(reference, amount, service_code, customer_reference, meta)` -> `ProviderResult("Success" | "Failed" | "Pending", provider_ref, message)`. **Send `reference` (our transaction id) to the provider as its idempotency/merchant reference** so a retry can never charge twice.
   - `status(reference, provider_ref)` -> `ProviderResult`; used by the 5-minute job for transactions still processing.
   - `refund(reference, provider_ref, amount)` -> `ProviderResult`.
   - `verify_webhook(raw_body, headers)` -> `{"reference", "status", "provider_ref", "message"}` or `None` when the signature is wrong.
2. Register it in `providers/registry.py` (`PROVIDERS["Fawry"] = FawryProvider`) and add its name to the *Payment Provider* options of Payment Settings.
3. Secrets: fill *Provider API Key*, *Provider Secret* and *Webhook Signing Secret* in Payment Settings (Password fields, encrypted in the database), or put `payment_network_provider_api_key`, `payment_network_provider_secret`, `payment_network_webhook_secret` in `site_config.json`. Read them with `self.secret("provider_secret")`. Never put a key in code.
4. Give the provider the callback address shown at the top of Payment Settings. Callbacks must carry `X-Signature: HMAC-SHA256(secret, raw body)`. Adapt `verify_webhook` if the provider signs differently.
5. Test every path in Sandbox first. With the `Mock` provider the cents choose the result: `.13` fails, `.77` stays pending then succeeds, `.99` stays pending then fails, anything else succeeds.
6. Only then set the mode to *Live*. Live mode refuses to start with the `Mock` provider.

Card data is never stored: the module keeps only the provider's reference and status.
