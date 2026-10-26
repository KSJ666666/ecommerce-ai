package com.spzx.file.config.test;

import io.minio.BucketExistsArgs;
import io.minio.MakeBucketArgs;
import io.minio.MinioClient;
import io.minio.UploadObjectArgs;
import io.minio.errors.MinioException;
import java.io.IOException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;

public class FileUploader {
  public static void main(String[] args)
      throws IOException, NoSuchAlgorithmException, InvalidKeyException {
    try {
      // 1. 构建 client（endpoint / accessKey / secretKey）
      MinioClient minioClient =
          MinioClient.builder()
              .endpoint("http://127.0.0.1:9000")
              .credentials("xEEsL2VZjpwFv4fF", "b4XwICeGaQyYYYcnvhOfv0Pf6EgmckIi")
              .build();

      // 2. bucket 不存在就建
      boolean found =
          minioClient.bucketExists(BucketExistsArgs.builder().bucket("spzx").build());
      if (!found) {
        minioClient.makeBucket(MakeBucketArgs.builder().bucket("spzx").build());
      } else {
        System.out.println("Bucket 'spzx' already exists.");
      }
      UploadObjectArgs build = UploadObjectArgs.builder()
              .bucket("spzx")
              .object("xiaoyu")
              .filename("D:/images/gyk/gyk001.jpg")
              .build();


      // 3. 上传本地文件：filename 是本地路径，object 是桶里的对象名
//      minioClient.uploadObject(
//          UploadObjectArgs.builder()
//              .bucket("asiatrip")
//              .object("asiaphotos-2015.zip")
//              .filename("/home/user/Photos/asiaphotos.zip")
//              .build());
      minioClient.uploadObject(build);

      System.out.println("upload success.");
    } catch (MinioException e) {
      System.out.println("Error occurred: " + e);
      System.out.println("HTTP trace: " + e.httpTrace());
    }
  }
}