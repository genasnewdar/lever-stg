-- CreateEnum
CREATE TYPE "UserType" AS ENUM ('STUDENT', 'INSTRUCTOR', 'ADMIN', 'TEACHING_ASSISTANT');

-- CreateEnum
CREATE TYPE "DifficultyLevel" AS ENUM ('BEGINNER', 'INTERMEDIATE', 'ADVANCED', 'EXPERT');

-- CreateEnum
CREATE TYPE "LessonType" AS ENUM ('VIDEO', 'TEXT', 'QUIZ', 'ASSIGNMENT', 'READING', 'INTERACTIVE');

-- CreateEnum
CREATE TYPE "EnrollmentStatus" AS ENUM ('ACTIVE', 'COMPLETED', 'DROPPED', 'SUSPENDED');

-- CreateEnum
CREATE TYPE "QuestionType" AS ENUM ('MULTIPLE_CHOICE', 'FILL_IN_THE_BLANK', 'SHORT_ANSWER', 'ESSAY', 'TRUE_FALSE', 'MATCHING', 'COLLOCATION_FORK', 'NUMERIC_ANSWER', 'FREE_RESPONSE');

-- CreateEnum
CREATE TYPE "TestSubject" AS ENUM ('MATH', 'ENGLISH', 'SCIENCE', 'PROGRAMMING', 'BUSINESS', 'DESIGN', 'OTHER');

-- CreateEnum
CREATE TYPE "TestAttemptStatus" AS ENUM ('CANCELED_BY_SYSTEM', 'IN_PROGRESS', 'SUBMITTED', 'GRADED');

-- CreateEnum
CREATE TYPE "SubmissionStatus" AS ENUM ('SUBMITTED', 'GRADED', 'RETURNED');

-- CreateTable
CREATE TABLE "t_user" (
    "id" SERIAL NOT NULL,
    "auth0_id" VARCHAR(255) NOT NULL,
    "phone" VARCHAR(255),
    "email" VARCHAR(255) NOT NULL,
    "type" "UserType" NOT NULL DEFAULT 'STUDENT',
    "full_name" VARCHAR(255) NOT NULL,
    "picture" VARCHAR(255),
    "bio" TEXT,
    "created_at" TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_deleted" BOOLEAN NOT NULL DEFAULT false,
    "login_count" INTEGER NOT NULL DEFAULT 0,
    "school_class_id" TEXT,

    CONSTRAINT "PK_user_id" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_school" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "address" TEXT,
    "logo" TEXT,

    CONSTRAINT "t_school_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_school_class" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "school_id" TEXT NOT NULL,

    CONSTRAINT "t_school_class_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_course" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "short_title" TEXT,
    "description" TEXT,
    "overview" TEXT,
    "learning_objectives" TEXT,
    "prerequisites" TEXT,
    "difficulty_level" "DifficultyLevel" NOT NULL DEFAULT 'BEGINNER',
    "estimated_duration" INTEGER,
    "language" TEXT NOT NULL DEFAULT 'en',
    "category" TEXT,
    "subcategory" TEXT,
    "thumbnail_url" TEXT,
    "video_preview_url" TEXT,
    "price" MONEY,
    "is_free" BOOLEAN NOT NULL DEFAULT false,
    "is_published" BOOLEAN NOT NULL DEFAULT false,
    "is_featured" BOOLEAN NOT NULL DEFAULT false,
    "rating" DOUBLE PRECISION DEFAULT 0,
    "rating_count" INTEGER NOT NULL DEFAULT 0,
    "enrollment_count" INTEGER NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "instructor_id" TEXT NOT NULL,
    "creator_id" TEXT NOT NULL,

    CONSTRAINT "t_course_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_module" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "order" INTEGER NOT NULL,
    "is_published" BOOLEAN NOT NULL DEFAULT true,
    "estimated_duration" INTEGER,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_module_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_lesson" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "content" TEXT,
    "video_url" TEXT,
    "video_duration" INTEGER,
    "order" INTEGER NOT NULL,
    "lesson_type" "LessonType" NOT NULL DEFAULT 'VIDEO',
    "is_published" BOOLEAN NOT NULL DEFAULT true,
    "is_preview" BOOLEAN NOT NULL DEFAULT false,
    "module_id" TEXT NOT NULL,

    CONSTRAINT "t_lesson_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_lesson_resource" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "file_url" TEXT NOT NULL,
    "file_type" TEXT NOT NULL,
    "file_size" INTEGER,
    "lesson_id" TEXT NOT NULL,

    CONSTRAINT "t_lesson_resource_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_enrollment" (
    "id" TEXT NOT NULL,
    "status" "EnrollmentStatus" NOT NULL DEFAULT 'ACTIVE',
    "enrolled_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "completed_at" TIMESTAMP(3),
    "last_accessed_at" TIMESTAMP(3),
    "progress_percentage" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "user_id" TEXT NOT NULL,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_enrollment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_course_progress" (
    "id" TEXT NOT NULL,
    "progress_percentage" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "time_spent" INTEGER NOT NULL DEFAULT 0,
    "last_accessed_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" TEXT NOT NULL,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_course_progress_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_module_progress" (
    "id" TEXT NOT NULL,
    "is_completed" BOOLEAN NOT NULL DEFAULT false,
    "completed_at" TIMESTAMP(3),
    "time_spent" INTEGER NOT NULL DEFAULT 0,
    "progress_percentage" DOUBLE PRECISION NOT NULL DEFAULT 0,
    "course_progress_id" TEXT NOT NULL,
    "module_id" TEXT NOT NULL,

    CONSTRAINT "t_module_progress_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_lesson_progress" (
    "id" TEXT NOT NULL,
    "is_completed" BOOLEAN NOT NULL DEFAULT false,
    "completed_at" TIMESTAMP(3),
    "time_spent" INTEGER NOT NULL DEFAULT 0,
    "watch_time" INTEGER NOT NULL DEFAULT 0,
    "module_progress_id" TEXT NOT NULL,
    "lesson_id" TEXT NOT NULL,

    CONSTRAINT "t_lesson_progress_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_test" (
    "id" TEXT NOT NULL,
    "duration" INTEGER NOT NULL,
    "subject" "TestSubject" NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "instructions" TEXT,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "t_test_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_section" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "instructions" TEXT,
    "order" INTEGER NOT NULL,
    "testId" TEXT NOT NULL,

    CONSTRAINT "t_section_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_task" (
    "id" TEXT NOT NULL,
    "title" TEXT,
    "instructions" TEXT,
    "passage" TEXT,
    "order" INTEGER NOT NULL,
    "sectionId" TEXT NOT NULL,

    CONSTRAINT "t_task_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_question" (
    "id" TEXT NOT NULL,
    "questionNumber" TEXT,
    "text" TEXT NOT NULL,
    "points" INTEGER NOT NULL,
    "type" "QuestionType" NOT NULL,
    "category" TEXT,
    "sectionId" TEXT,
    "taskId" TEXT,
    "correctNumericAnswer" DOUBLE PRECISION,
    "correctFormulaLatex" TEXT,
    "matchingItems" JSONB,
    "correctMapping" JSONB,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "t_question_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_option" (
    "id" TEXT NOT NULL,
    "label" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "order" INTEGER NOT NULL,
    "is_correct" BOOLEAN NOT NULL DEFAULT false,
    "questionId" TEXT NOT NULL,

    CONSTRAINT "t_option_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_test_attempt" (
    "id" TEXT NOT NULL,
    "user_id" TEXT NOT NULL,
    "test_id" TEXT NOT NULL,
    "status" "TestAttemptStatus" NOT NULL DEFAULT 'IN_PROGRESS',
    "started_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "submitted_at" TIMESTAMP(3),
    "due_at" TIMESTAMP(3),
    "report" TEXT,
    "score" DOUBLE PRECISION,
    "finish_id" TEXT,

    CONSTRAINT "t_test_attempt_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_response" (
    "id" TEXT NOT NULL,
    "attempt_id" TEXT NOT NULL,
    "question_id" TEXT NOT NULL,
    "answer_text" TEXT,
    "numeric_answer" DOUBLE PRECISION,
    "selected_option" TEXT,
    "additional_data" JSONB,
    "is_correct" BOOLEAN,
    "points_awarded" INTEGER,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "t_response_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_assignment" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "instructions" TEXT,
    "due_date" TIMESTAMP(3),
    "points" INTEGER NOT NULL DEFAULT 100,
    "is_published" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_assignment_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_assignment_submission" (
    "id" TEXT NOT NULL,
    "submission_text" TEXT,
    "file_urls" TEXT[],
    "submitted_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "status" "SubmissionStatus" NOT NULL DEFAULT 'SUBMITTED',
    "grade" DOUBLE PRECISION,
    "feedback" TEXT,
    "graded_at" TIMESTAMP(3),
    "user_id" TEXT NOT NULL,
    "assignment_id" TEXT NOT NULL,

    CONSTRAINT "t_assignment_submission_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_forum" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "is_active" BOOLEAN NOT NULL DEFAULT true,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_forum_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_forum_post" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "is_pinned" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "author_id" TEXT NOT NULL,
    "forum_id" TEXT NOT NULL,

    CONSTRAINT "t_forum_post_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_forum_reply" (
    "id" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP(3) NOT NULL,
    "author_id" TEXT NOT NULL,
    "post_id" TEXT NOT NULL,

    CONSTRAINT "t_forum_reply_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_announcement" (
    "id" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "content" TEXT NOT NULL,
    "is_important" BOOLEAN NOT NULL DEFAULT false,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_announcement_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_certificate" (
    "id" TEXT NOT NULL,
    "certificate_url" TEXT NOT NULL,
    "issued_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "is_valid" BOOLEAN NOT NULL DEFAULT true,
    "user_id" TEXT NOT NULL,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_certificate_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "t_course_review" (
    "id" TEXT NOT NULL,
    "rating" INTEGER NOT NULL,
    "review_text" TEXT,
    "created_at" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "user_id" TEXT NOT NULL,
    "course_id" TEXT NOT NULL,

    CONSTRAINT "t_course_review_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "t_user_auth0_id_key" ON "t_user"("auth0_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_user_phone_key" ON "t_user"("phone");

-- CreateIndex
CREATE UNIQUE INDEX "t_user_email_key" ON "t_user"("email");

-- CreateIndex
CREATE UNIQUE INDEX "t_enrollment_user_id_course_id_key" ON "t_enrollment"("user_id", "course_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_course_progress_user_id_course_id_key" ON "t_course_progress"("user_id", "course_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_module_progress_course_progress_id_module_id_key" ON "t_module_progress"("course_progress_id", "module_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_lesson_progress_module_progress_id_lesson_id_key" ON "t_lesson_progress"("module_progress_id", "lesson_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_assignment_submission_user_id_assignment_id_key" ON "t_assignment_submission"("user_id", "assignment_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_certificate_user_id_course_id_key" ON "t_certificate"("user_id", "course_id");

-- CreateIndex
CREATE UNIQUE INDEX "t_course_review_user_id_course_id_key" ON "t_course_review"("user_id", "course_id");

-- AddForeignKey
ALTER TABLE "t_user" ADD CONSTRAINT "t_user_school_class_id_fkey" FOREIGN KEY ("school_class_id") REFERENCES "t_school_class"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_school_class" ADD CONSTRAINT "t_school_class_school_id_fkey" FOREIGN KEY ("school_id") REFERENCES "t_school"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_course" ADD CONSTRAINT "t_course_instructor_id_fkey" FOREIGN KEY ("instructor_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_course" ADD CONSTRAINT "t_course_creator_id_fkey" FOREIGN KEY ("creator_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_module" ADD CONSTRAINT "t_module_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_lesson" ADD CONSTRAINT "t_lesson_module_id_fkey" FOREIGN KEY ("module_id") REFERENCES "t_module"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_lesson_resource" ADD CONSTRAINT "t_lesson_resource_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "t_lesson"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_enrollment" ADD CONSTRAINT "t_enrollment_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_enrollment" ADD CONSTRAINT "t_enrollment_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_course_progress" ADD CONSTRAINT "t_course_progress_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_course_progress" ADD CONSTRAINT "t_course_progress_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_module_progress" ADD CONSTRAINT "t_module_progress_course_progress_id_fkey" FOREIGN KEY ("course_progress_id") REFERENCES "t_course_progress"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_module_progress" ADD CONSTRAINT "t_module_progress_module_id_fkey" FOREIGN KEY ("module_id") REFERENCES "t_module"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_lesson_progress" ADD CONSTRAINT "t_lesson_progress_module_progress_id_fkey" FOREIGN KEY ("module_progress_id") REFERENCES "t_module_progress"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_lesson_progress" ADD CONSTRAINT "t_lesson_progress_lesson_id_fkey" FOREIGN KEY ("lesson_id") REFERENCES "t_lesson"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_section" ADD CONSTRAINT "t_section_testId_fkey" FOREIGN KEY ("testId") REFERENCES "t_test"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_task" ADD CONSTRAINT "t_task_sectionId_fkey" FOREIGN KEY ("sectionId") REFERENCES "t_section"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_question" ADD CONSTRAINT "t_question_sectionId_fkey" FOREIGN KEY ("sectionId") REFERENCES "t_section"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_question" ADD CONSTRAINT "t_question_taskId_fkey" FOREIGN KEY ("taskId") REFERENCES "t_task"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_option" ADD CONSTRAINT "t_option_questionId_fkey" FOREIGN KEY ("questionId") REFERENCES "t_question"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_test_attempt" ADD CONSTRAINT "t_test_attempt_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_test_attempt" ADD CONSTRAINT "t_test_attempt_test_id_fkey" FOREIGN KEY ("test_id") REFERENCES "t_test"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_response" ADD CONSTRAINT "t_response_attempt_id_fkey" FOREIGN KEY ("attempt_id") REFERENCES "t_test_attempt"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_response" ADD CONSTRAINT "t_response_question_id_fkey" FOREIGN KEY ("question_id") REFERENCES "t_question"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_assignment" ADD CONSTRAINT "t_assignment_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_assignment_submission" ADD CONSTRAINT "t_assignment_submission_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_assignment_submission" ADD CONSTRAINT "t_assignment_submission_assignment_id_fkey" FOREIGN KEY ("assignment_id") REFERENCES "t_assignment"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_forum" ADD CONSTRAINT "t_forum_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_forum_post" ADD CONSTRAINT "t_forum_post_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_forum_post" ADD CONSTRAINT "t_forum_post_forum_id_fkey" FOREIGN KEY ("forum_id") REFERENCES "t_forum"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_forum_reply" ADD CONSTRAINT "t_forum_reply_author_id_fkey" FOREIGN KEY ("author_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_forum_reply" ADD CONSTRAINT "t_forum_reply_post_id_fkey" FOREIGN KEY ("post_id") REFERENCES "t_forum_post"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_announcement" ADD CONSTRAINT "t_announcement_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_certificate" ADD CONSTRAINT "t_certificate_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_certificate" ADD CONSTRAINT "t_certificate_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_course_review" ADD CONSTRAINT "t_course_review_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "t_user"("auth0_id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "t_course_review" ADD CONSTRAINT "t_course_review_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "t_course"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
