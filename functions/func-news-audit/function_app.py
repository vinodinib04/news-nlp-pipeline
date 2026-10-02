import logging
import azure.functions as func

app = func.FunctionApp()


@app.event_grid_trigger(arg_name="azeventgrid")
def lognewsaudit(azeventgrid: func.EventGridEvent):
    logging.info("Audit Event Grid trigger processed an event")

    logging.info("Event subject: %s", azeventgrid.subject)
    logging.info("Event type: %s", azeventgrid.event_type)
    logging.info("Event data: %s", azeventgrid.get_json())