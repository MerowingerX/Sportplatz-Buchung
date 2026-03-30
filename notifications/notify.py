from __future__ import annotations

import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import aiosmtplib

from datetime import date
from booking.models import Booking, Series, User
from web.config import Settings

logger = logging.getLogger(__name__)


async def _send_email(to: str, subject: str, body: str, settings: Settings, cc: list[str] = []) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    if cc:
        msg["Cc"] = ", ".join(cc)
    msg.attach(MIMEText(body, "plain", "utf-8"))
    all_recipients = [to] + cc

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            start_tls=True,
            recipients=all_recipients,
        )
    except Exception as e:
        logger.error("E-Mail-Versand fehlgeschlagen an %s: %s", to, e)


async def send_booking_confirmation(booking: Booking, user: User, settings: Settings, cc: list[str] = []) -> None:
    subject = f"Buchungsbestätigung: {booking.field.value} am {booking.date}"
    body = (
        f"Hallo {user.name},\n\n"
        f"deine Buchung wurde bestätigt:\n\n"
        f"  Platz:    {booking.field.value}\n"
        f"  Datum:    {booking.date.strftime('%d.%m.%Y')}\n"
        f"  Uhrzeit:  {booking.start_time.strftime('%H:%M')} – {booking.end_time.strftime('%H:%M')}\n"
        f"  Art:      {booking.booking_type.value}\n"
    )
    if booking.sunset_note:
        body += f"\n⚠️  {booking.sunset_note}\n"
    body += "\nViel Spaß auf dem Platz!\n"
    await _send_email(user.email, subject, body, settings, cc=cc)


async def send_cancellation_notice(booking: Booking, user: User, settings: Settings, cc: list[str] = []) -> None:
    subject = f"Buchung storniert: {booking.field.value} am {booking.date}"
    body = (
        f"Hallo {user.name},\n\n"
        f"deine Buchung wurde storniert:\n\n"
        f"  Platz:    {booking.field.value}\n"
        f"  Datum:    {booking.date.strftime('%d.%m.%Y')}\n"
        f"  Uhrzeit:  {booking.start_time.strftime('%H:%M')} – {booking.end_time.strftime('%H:%M')}\n\n"
        f"Bei Fragen wende dich an den Administrator.\n"
    )
    await _send_email(user.email, subject, body, settings, cc=cc)


async def send_dfbnet_displacement_notice(
    displaced_booking: Booking,
    displaced_user: User,
    new_dfbnet_booking: Booking,
    settings: Settings,
) -> None:
    subject = f"Deine Buchung wurde durch DFBnet ersetzt – {displaced_booking.date.strftime('%d.%m.%Y')}"
    body = (
        f"Hallo {displaced_user.name},\n\n"
        f"deine Buchung musste leider durch ein DFB-Pflichtspiel verdrängt werden:\n\n"
        f"  Stornierte Buchung:\n"
        f"    Platz:   {displaced_booking.field.value}\n"
        f"    Datum:   {displaced_booking.date.strftime('%d.%m.%Y')}\n"
        f"    Uhrzeit: {displaced_booking.start_time.strftime('%H:%M')} – {displaced_booking.end_time.strftime('%H:%M')}\n\n"
        f"  DFBnet-Pflichtspiel:\n"
        f"    Platz:   {new_dfbnet_booking.field.value}\n"
        f"    Datum:   {new_dfbnet_booking.date.strftime('%d.%m.%Y')}\n"
        f"    Uhrzeit: {new_dfbnet_booking.start_time.strftime('%H:%M')} – {new_dfbnet_booking.end_time.strftime('%H:%M')}\n\n"
        f"Bitte buche einen anderen Termin. Wir bitten um Verständnis.\n\n"
        f"Zur Buchung: {settings.booking_url}\n"
    )
    await _send_email(displaced_user.email, subject, body, settings)


async def send_series_confirmation(
    series: Series,
    created: list[Booking],
    skipped: list[date],
    admin: User,
    settings: Settings,
) -> None:
    if not created:
        return
    first = created[0]
    subject = f"Serie angelegt: {series.mannschaft or first.field.value}"

    created_list = "\n".join(
        f"  - {b.date.strftime('%d.%m.%Y')} {b.start_time.strftime('%H:%M')}–{b.end_time.strftime('%H:%M')}"
        for b in created
    )
    body = (
        f"Hallo {admin.name},\n\n"
        f"die Serienbuchung wurde erfolgreich angelegt:\n\n"
        f"  Platz:      {first.field.value}\n"
        f"  Mannschaft: {series.mannschaft or '–'}\n"
        f"  Rhythmus:   {series.rhythm.value}\n\n"
        f"Angelegte Termine ({len(created)}):\n"
        f"{created_list}\n"
    )

    if skipped:
        skipped_list = "\n".join(
            f"  - {d.strftime('%d.%m.%Y')}" for d in skipped
        )
        body += (
            f"\n⚠️  Übersprungene Termine ({len(skipped)}) wegen Konflikt oder Sperrzeit:\n"
            f"{skipped_list}\n"
        )

    body += "\nBei Fragen wende dich an den Administrator.\n"
    await _send_email(admin.email, subject, body, settings)




async def send_series_cancellation_notice(
    cancelled_bookings: list[Booking],
    user: User,
    settings: Settings,
) -> None:
    if not cancelled_bookings:
        return
    first = cancelled_bookings[0]
    subject = f"Serienbuchung beendet: {first.field.value}"
    dates_list = "\n".join(
        f"  - {b.date.strftime('%d.%m.%Y')} {b.start_time.strftime('%H:%M')}–{b.end_time.strftime('%H:%M')}"
        for b in cancelled_bookings
    )
    body = (
        f"Hallo {user.name},\n\n"
        f"deine Serienbuchung wurde beendet. Folgende zukünftige Termine wurden storniert:\n\n"
        f"{dates_list}\n\n"
        f"Bei Fragen wende dich an den Administrator.\n"
    )
    await _send_email(user.email, subject, body, settings)
