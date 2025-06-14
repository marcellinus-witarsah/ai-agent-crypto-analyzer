from datetime import datetime
from src.utils.logger import logger
from src.utils.minio_ops import MinioOPS
from io import BytesIO
import pandas as pd
from src.utils.timescaledb_ops import TimescaleDBOps
from dotenv import load_dotenv
import os


class DataPipeline:
    def __init__(self, pair: str, batch_size: int, start_date: datetime, end_date: datetime):
        load_dotenv()
        self.pair = pair
        self.batch_size = batch_size
        self.start_date = start_date
        self.end_date = end_date

    def run(self):
        logger.info(
            f"Data will be ingested from MinIO to TimescaleDB ({self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')})"
        )
        try:
            ####################################################################
            # 1. READ DATA FROM MINIO
            ####################################################################
            logger.info("Ingesting data from MinIO ...")
            minio_ops = MinioOPS()
            data = minio_ops.read_object(
                bucket_name=os.getenv("BUCKET_NAME"),
                object_name=f"{self.start_date.strftime('%Y%m%d')}_{self.end_date.strftime('%Y%m%d')}_{self.pair}_ohlc_four_hourly.parquet",
            )
            df = pd.read_parquet(BytesIO(data))

            ####################################################################
            # 2. INSERT DATA INTO MINIO
            ####################################################################
            db_ops = TimescaleDBOps()
            
            # Implement batch insert
            for idx in range(0, len(df), self.batch_size):
                df_chunk = df.iloc[idx:idx+self.batch_size]
                data = [
                    [
                        datetime.strftime(
                            datetime.fromtimestamp(row["time"]), "%Y-%m-%dT%H:%M:%S.%fZ"
                        ),
                        self.pair,
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row["volume"]),
                        int(row["count"]),
                    ] for _, row in df_chunk.iterrows()
                ]
                db_ops.batch_insert_data(
                    "ohlc_four_hourly",
                    columns=("time","pair","open","high","low","close","count","volume"),
                    data=data,
                    conflict_column="time"
                )
            logger.info("Data ingestion process completed successfully.")
        except Exception as e:
            logger.error(
                f"An error occurred during the data pipeline ingestion process: {e}"
            )
            return