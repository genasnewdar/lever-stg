/*
  Warnings:

  - The values [SCIENCE,PROGRAMMING,BUSINESS,DESIGN,OTHER] on the enum `TestSubject` will be removed. If these variants are still used in the database, this will fail.
  - You are about to drop the column `created_at` on the `t_question` table. All the data in the column will be lost.
  - You are about to drop the column `updated_at` on the `t_question` table. All the data in the column will be lost.
  - You are about to drop the column `created_at` on the `t_test` table. All the data in the column will be lost.
  - You are about to drop the column `updated_at` on the `t_test` table. All the data in the column will be lost.
  - Added the required column `updatedAt` to the `t_question` table without a default value. This is not possible if the table is not empty.
  - Added the required column `updatedAt` to the `t_test` table without a default value. This is not possible if the table is not empty.

*/
-- AlterEnum
BEGIN;
CREATE TYPE "TestSubject_new" AS ENUM ('MATH', 'ENGLISH');
ALTER TABLE "t_test" ALTER COLUMN "subject" TYPE "TestSubject_new" USING ("subject"::text::"TestSubject_new");
ALTER TYPE "TestSubject" RENAME TO "TestSubject_old";
ALTER TYPE "TestSubject_new" RENAME TO "TestSubject";
DROP TYPE "TestSubject_old";
COMMIT;

-- AlterTable
ALTER TABLE "t_question" DROP COLUMN "created_at",
DROP COLUMN "updated_at",
ADD COLUMN     "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "updatedAt" TIMESTAMP(3) NOT NULL;

-- AlterTable
ALTER TABLE "t_test" DROP COLUMN "created_at",
DROP COLUMN "updated_at",
ADD COLUMN     "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN     "updatedAt" TIMESTAMP(3) NOT NULL;
