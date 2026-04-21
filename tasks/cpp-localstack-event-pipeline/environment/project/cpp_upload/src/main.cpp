#include <curl/curl.h>

#include <fstream>
#include <iostream>
#include <string>

extern "C" size_t read_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
  auto* in = static_cast<std::ifstream*>(userdata);
  in->read(ptr, static_cast<std::streamsize>(size * nmemb));
  return static_cast<size_t>(in->gcount());
}

int main(int argc, char** argv) {
  if (argc != 3) {
    std::cerr << "usage: s3_put <presigned-url> <file-path>\n";
    return 2;
  }

  std::ifstream in(argv[2], std::ios::binary);
  if (!in) {
    std::cerr << "failed to open input file\n";
    return 1;
  }

  in.seekg(0, std::ios::end);
  const auto len = static_cast<curl_off_t>(in.tellg());
  in.seekg(0, std::ios::beg);

  CURL* curl = curl_easy_init();
  if (!curl) {
    std::cerr << "curl_easy_init failed\n";
    return 1;
  }

  curl_easy_setopt(curl, CURLOPT_URL, argv[1]);
  curl_easy_setopt(curl, CURLOPT_UPLOAD, 1L);
  curl_easy_setopt(curl, CURLOPT_READFUNCTION, read_callback);
  curl_easy_setopt(curl, CURLOPT_READDATA, &in);
  curl_easy_setopt(curl, CURLOPT_INFILESIZE_LARGE, len);

  const CURLcode res = curl_easy_perform(curl);
  long http = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
  curl_easy_cleanup(curl);

  if (res != CURLE_OK) {
    std::cerr << "curl_easy_perform: " << curl_easy_strerror(res) << '\n';
    return 1;
  }
  if (http < 200 || http >= 300) {
    std::cerr << "HTTP " << http << '\n';
    return 1;
  }
  return 0;
}
