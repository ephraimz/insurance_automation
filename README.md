# Insurance Automation

This is the insurance automation module, which at the moment supports
working with the following resources:

* Ayalon
* Bituach Yashir
* Har
* Harel
* Menora
* Migdal
* Phoenix

You can import the needed resource from `insurance_automation.resources`.

For example:

    from insurance_automation.resources import Harel

## Insurance providers

If you’re working with an insurance provider website, use the `authenticate` method to authenticate, and then the `confirm_authentication` method to confirm the authentication with the received SMS code.

## Persisting state

If a new instance of the resource class is created for sending subsequent requests, set `resource.session` (the requests session) and `resource.data` (other data).
