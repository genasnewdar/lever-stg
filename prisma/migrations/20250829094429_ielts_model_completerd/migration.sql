-- CreateEnum
CREATE TYPE "IeltsModule" AS ENUM ('LISTENING', 'READING', 'WRITING', 'SPEAKING');

-- CreateEnum
CREATE TYPE "IeltsQuestionType" AS ENUM ('MULTIPLE_CHOICE', 'MATCHING', 'PLAN_MAP_DIAGRAM_LABELLING', 'FORM_NOTE_TABLE_FLOW_CHART_SUMMARY_COMPLETION', 'SENTENCE_COMPLETION', 'SHORT_ANSWER_QUESTIONS', 'MULTIPLE_CHOICE_READING', 'IDENTIFYING_INFORMATION', 'IDENTIFYING_WRITERS_VIEWS', 'MATCHING_INFORMATION', 'MATCHING_HEADINGS', 'MATCHING_FEATURES', 'MATCHING_SENTENCE_ENDINGS', 'SENTENCE_COMPLETION_READING', 'SUMMARY_NOTE_TABLE_FLOW_CHART_COMPLETION', 'DIAGRAM_LABEL_COMPLETION', 'SHORT_ANSWER_QUESTIONS_READING', 'TASK_1_ACADEMIC', 'TASK_1_GENERAL', 'TASK_2', 'PART_1', 'PART_2', 'PART_3');

-- CreateEnum
CREATE TYPE "IeltsTestStatus" AS ENUM ('DRAFT', 'ACTIVE', 'ARCHIVED', 'INACTIVE');

-- CreateEnum
CREATE TYPE "IeltsAttemptStatus" AS ENUM ('NOT_STARTED', 'IN_PROGRESS', 'LISTENING_COMPLETED', 'READING_COMPLETED', 'WRITING_COMPLETED', 'SPEAKING_SCHEDULED', 'SPEAKING_IN_PROGRESS', 'SPEAKING_COMPLETED', 'FULLY_COMPLETED', 'GRADED', 'EXPIRED', 'CANCELLED');

-- CreateEnum
CREATE TYPE "SpeakingSessionStatus" AS ENUM ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED', 'NO_SHOW');

-- CreateTable
CREATE TABLE "t_ielts_test" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "status" "IeltsTestStatus" NOT NULL DEFAULT 'DRAFT',
    "duration_minutes" INTEGER NOT NULL DEFAULT 180,
    "is_practice" BOOLEAN NOT NULL DEFAULT true,
    "version" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "published_at" TIMESTAMP(3),

    CONSTRAINT "t_ielts_test_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_listening_test" (
    "id" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL DEFAULT 40,
    "instructions" TEXT,
    "audio_url" TEXT,
    "test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_listening_test_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_listening_section" (
    "id" TEXT NOT NULL,
    "section_number" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "context" TEXT,
    "audio_url" TEXT,
    "audio_start_time" INTEGER,
    "audio_end_time" INTEGER,
    "instructions" TEXT,
    "listening_test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_listening_section_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_listening_question" (
    "id" TEXT NOT NULL,
    "question_number" INTEGER NOT NULL,
    "question_text" TEXT,
    "question_type" "IeltsQuestionType" NOT NULL,
    "points" DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "audio_start_time" INTEGER,
    "audio_end_time" INTEGER,
    "section_id" TEXT NOT NULL,
    "correct_answer" TEXT,
    "matching_pairs" JSONB,
    "additional_data" JSONB,

    CONSTRAINT "t_ielts_listening_question_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_listening_option" (
    "id" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "is_correct" BOOLEAN NOT NULL DEFAULT false,
    "order" INTEGER NOT NULL,
    "question_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_listening_option_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_reading_test" (
    "id" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL DEFAULT 60,
    "instructions" TEXT,
    "test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_reading_test_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_reading_passage" (
    "id" TEXT NOT NULL,
    "passage_number" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "word_count" INTEGER,
    "source" TEXT,
    "reading_test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_reading_passage_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_reading_question" (
    "id" TEXT NOT NULL,
    "question_number" INTEGER NOT NULL,
    "question_text" TEXT,
    "question_type" "IeltsQuestionType" NOT NULL,
    "points" DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    "instructions" TEXT,
    "passage_id" TEXT NOT NULL,
    "correct_answer" TEXT,
    "matching_data" JSONB,
    "additional_data" JSONB,

    CONSTRAINT "t_ielts_reading_question_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_reading_option" (
    "id" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "is_correct" BOOLEAN NOT NULL DEFAULT false,
    "order" INTEGER NOT NULL,
    "question_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_reading_option_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_writing_test" (
    "id" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL DEFAULT 60,
    "instructions" TEXT,
    "test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_writing_test_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_writing_task" (
    "id" TEXT NOT NULL,
    "task_number" INTEGER NOT NULL,
    "task_type" "IeltsQuestionType" NOT NULL,
    "title" TEXT NOT NULL,
    "prompt" TEXT NOT NULL,
    "min_words" INTEGER NOT NULL DEFAULT 150,
    "suggested_time" INTEGER NOT NULL,
    "visual_content" TEXT,
    "writing_test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_writing_task_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_speaking_test" (
    "id" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL DEFAULT 15,
    "instructions" TEXT,
    "test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_speaking_test_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_speaking_part" (
    "id" TEXT NOT NULL,
    "part_number" INTEGER NOT NULL,
    "title" TEXT NOT NULL,
    "duration_minutes" INTEGER NOT NULL,
    "instructions" TEXT,
    "speaking_test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_speaking_part_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_speaking_question" (
    "id" TEXT NOT NULL,
    "question_text" TEXT NOT NULL,
    "question_type" "IeltsQuestionType" NOT NULL,
    "preparation_time" INTEGER,
    "speaking_time" INTEGER,
    "cue_card" TEXT,
    "follow_up_notes" TEXT,
    "part_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_speaking_question_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_test_attempt" (
    "id" TEXT NOT NULL,
    "attempt_number" INTEGER NOT NULL DEFAULT 1,
    "status" "IeltsAttemptStatus" NOT NULL DEFAULT 'NOT_STARTED',
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "listening_completed_at" TIMESTAMP(3),
    "reading_completed_at" TIMESTAMP(3),
    "writing_completed_at" TIMESTAMP(3),
    "speaking_completed_at" TIMESTAMP(3),
    "submitted_at" TIMESTAMP(3),
    "expires_at" TIMESTAMP(3),
    "listening_score" DOUBLE PRECISION,
    "reading_score" DOUBLE PRECISION,
    "writing_score" DOUBLE PRECISION,
    "speaking_score" DOUBLE PRECISION,
    "listening_band" DOUBLE PRECISION,
    "reading_band" DOUBLE PRECISION,
    "writing_band" DOUBLE PRECISION,
    "speaking_band" DOUBLE PRECISION,
    "overall_band" DOUBLE PRECISION,
    "time_spent_seconds" INTEGER NOT NULL DEFAULT 0,
    "grading_notes" TEXT,
    "feedback" TEXT,
    "user_id" TEXT NOT NULL,
    "test_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_test_attempt_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_listening_response" (
    "id" TEXT NOT NULL,
    "answer" TEXT,
    "is_correct" BOOLEAN,
    "time_spent" INTEGER,
    "attempt_id" TEXT NOT NULL,
    "question_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_listening_response_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_reading_response" (
    "id" TEXT NOT NULL,
    "answer" TEXT,
    "is_correct" BOOLEAN,
    "time_spent" INTEGER,
    "attempt_id" TEXT NOT NULL,
    "question_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_reading_response_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_writing_response" (
    "id" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "word_count" INTEGER,
    "time_spent" INTEGER,
    "task_achievement" DOUBLE PRECISION,
    "coherence_cohesion" DOUBLE PRECISION,
    "lexical_resource" DOUBLE PRECISION,
    "grammar_accuracy" DOUBLE PRECISION,
    "band_score" DOUBLE PRECISION,
    "grader_feedback" TEXT,
    "graded_at" TIMESTAMP(3),
    "graded_by" TEXT,
    "attempt_id" TEXT NOT NULL,
    "task_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_writing_response_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_speaking_response" (
    "id" TEXT NOT NULL,
    "audio_url" TEXT,
    "transcript" TEXT,
    "duration" INTEGER,
    "fluency_coherence" DOUBLE PRECISION,
    "lexical_resource" DOUBLE PRECISION,
    "grammar_accuracy" DOUBLE PRECISION,
    "pronunciation" DOUBLE PRECISION,
    "band_score" DOUBLE PRECISION,
    "grader_feedback" TEXT,
    "graded_at" TIMESTAMP(3),
    "graded_by" TEXT,
    "attempt_id" TEXT NOT NULL,
    "question_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_speaking_response_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_speaking_session" (
    "id" TEXT NOT NULL,
    "status" "SpeakingSessionStatus" NOT NULL DEFAULT 'SCHEDULED',
    "scheduled_at" TIMESTAMP(3) NOT NULL,
    "started_at" TIMESTAMP(3),
    "completed_at" TIMESTAMP(3),
    "duration_minutes" INTEGER,
    "examiner_id" TEXT,
    "session_notes" TEXT,
    "technical_issues" TEXT,
    "attempt_id" TEXT NOT NULL,

    CONSTRAINT "t_ielts_speaking_session_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_band_conversion" (
    "id" TEXT NOT NULL,
    "module" "IeltsModule" NOT NULL,
    "raw_score" INTEGER NOT NULL,
    "band_score" DOUBLE PRECISION NOT NULL,

    CONSTRAINT "t_ielts_band_conversion_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_vocabulary" (
    "id" TEXT NOT NULL,
    "word" TEXT NOT NULL,
    "definition" TEXT NOT NULL,
    "part_of_speech" TEXT,
    "example_sentence" TEXT,
    "difficulty_level" TEXT,
    "frequency" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "t_ielts_vocabulary_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_grammar_point" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "examples" JSONB NOT NULL,
    "difficulty_level" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "t_ielts_grammar_point_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_ielts_study_material" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "material_type" TEXT NOT NULL,
    "module" "IeltsModule" NOT NULL,
    "difficulty_level" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "t_ielts_study_material_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_listening_test_test_id_key" ON "t_ielts_listening_test"("test_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_reading_test_test_id_key" ON "t_ielts_reading_test"("test_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_writing_test_test_id_key" ON "t_ielts_writing_test"("test_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_speaking_test_test_id_key" ON "t_ielts_speaking_test"("test_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_listening_response_attempt_id_question_id_key" ON "t_ielts_listening_response"("attempt_id", "question_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_reading_response_attempt_id_question_id_key" ON "t_ielts_reading_response"("attempt_id", "question_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_writing_response_attempt_id_task_id_key" ON "t_ielts_writing_response"("attempt_id", "task_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_speaking_response_attempt_id_question_id_key" ON "t_ielts_speaking_response"("attempt_id", "question_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_band_conversion_module_raw_score_key" ON "t_ielts_band_conversion"("module", "raw_score");

-- CreateIndex
CREATE UNIQUE INDEX "t_ielts_vocabulary_word_key" ON "t_ielts_vocabulary"("word");

-- AddForeignKey
ALTER TABLE "t_ielts_listening_test" ADD CONSTRAINT "t_ielts_listening_test_test_id_fkey" FOREIGN KEY ("test_id") REFERENCES "t_ielts_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_listening_section" ADD CONSTRAINT "t_ielts_listening_section_listening_test_id_fkey" FOREIGN KEY ("listening_test_id") REFERENCES "t_ielts_listening_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_listening_question" ADD CONSTRAINT "t_ielts_listening_question_section_id_fkey" FOREIGN KEY ("section_id") REFERENCES "t_ielts_listening_section"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_listening_option" ADD CONSTRAINT "t_ielts_listening_option_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "t_ielts_listening_question"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_reading_test" ADD CONSTRAINT "t_ielts_reading_test_test_id_fkey" FOREIGN KEY ("test_id") REFERENCES "t_ielts_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_reading_passage" ADD CONSTRAINT "t_ielts_reading_passage_reading_test_id_fkey" FOREIGN KEY ("reading_test_id") REFERENCES "t_ielts_reading_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_reading_question" ADD CONSTRAINT "t_ielts_reading_question_passage_id_fkey" FOREIGN KEY ("passage_id") REFERENCES "t_ielts_reading_passage"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_reading_option" ADD CONSTRAINT "t_ielts_reading_option_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "t_ielts_reading_question"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_writing_test" ADD CONSTRAINT "t_ielts_writing_test_test_id_fkey" FOREIGN KEY ("test_id") REFERENCES "t_ielts_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_writing_task" ADD CONSTRAINT "t_ielts_writing_task_writing_test_id_fkey" FOREIGN KEY ("writing_test_id") REFERENCES "t_ielts_writing_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_speaking_test" ADD CONSTRAINT "t_ielts_speaking_test_test_id_fkey" FOREIGN KEY ("test_id") REFERENCES "t_ielts_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_speaking_part" ADD CONSTRAINT "t_ielts_speaking_part_speaking_test_id_fkey" FOREIGN KEY ("speaking_test_id") REFERENCES "t_ielts_speaking_test"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_speaking_question" ADD CONSTRAINT "t_ielts_speaking_question_part_id_fkey" FOREIGN KEY ("part_id") REFERENCES "t_ielts_speaking_part"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_test_attempt" ADD CONSTRAINT "t_ielts_test_attempt_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_test_attempt" ADD CONSTRAINT "t_ielts_test_attempt_test_id_fkey" FOREIGN KEY ("test_id") REFERENCES "t_ielts_test"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_listening_response" ADD CONSTRAINT "t_ielts_listening_response_attempt_id_fkey" FOREIGN KEY ("attempt_id") REFERENCES "t_ielts_test_attempt"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_listening_response" ADD CONSTRAINT "t_ielts_listening_response_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "t_ielts_listening_question"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_reading_response" ADD CONSTRAINT "t_ielts_reading_response_attempt_id_fkey" FOREIGN KEY ("attempt_id") REFERENCES "t_ielts_test_attempt"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_reading_response" ADD CONSTRAINT "t_ielts_reading_response_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "t_ielts_reading_question"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_writing_response" ADD CONSTRAINT "t_ielts_writing_response_attempt_id_fkey" FOREIGN KEY ("attempt_id") REFERENCES "t_ielts_test_attempt"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_writing_response" ADD CONSTRAINT "t_ielts_writing_response_task_id_fkey" FOREIGN KEY ("task_id") REFERENCES "t_ielts_writing_task"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_speaking_response" ADD CONSTRAINT "t_ielts_speaking_response_attempt_id_fkey" FOREIGN KEY ("attempt_id") REFERENCES "t_ielts_test_attempt"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_speaking_response" ADD CONSTRAINT "t_ielts_speaking_response_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "t_ielts_speaking_question"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_ielts_speaking_session" ADD CONSTRAINT "t_ielts_speaking_session_attempt_id_fkey" FOREIGN KEY ("attempt_id") REFERENCES "t_ielts_test_attempt"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
