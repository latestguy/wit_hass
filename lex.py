import boto3
import wave

AWS_ACCESS_KEY_ID = "AKIA2RRKR7U7PGVGVE4S"
AWS_SECRET_ACCESS_KEY = "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"

# set up AWS credentials
client = boto3.client('lex-runtime',
                      aws_access_key_id=AWS_ACCESS_KEY_ID,
                      aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                      region_name='us-east-1')

def transcribe_audio(audio_file):
    # transcribe audio to text
    transcribe = boto3.client('transcribe',
                              aws_access_key_id=AWS_ACCESS_KEY_ID,
                              aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                              region_name='us-east-1')

    job_name = audio_file[:-4] + '-job'
    job_uri = 's3://{}/{}'.format(S3_BUCKET, audio_file)

    transcribe.start_transcription_job(TranscriptionJobName=job_name,
                                       Media={'MediaFileUri': job_uri},
                                       MediaFormat='wav',
                                       LanguageCode='en-US')

    while True:
        status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
        if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
            break

    transcribed_text_uri = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
    transcribed_text = boto3.client('s3').get_object(Bucket=S3_BUCKET,
                                                     Key=transcribed_text_uri[transcribed_text_uri.index(job_name):])[
        'Body'].read().decode('utf-8')

    return transcribed_text